# Oryntela Privacy and Terms professional-review package

> **FACTUAL ADVISER HANDOFF — NOT LEGAL ADVICE OR APPROVED PUBLIC COPY**
>
> Prepared 11 September 2026 from repository baseline
> `c564a3164d2e202c6f407b7f8ef7d0111e1e23e3` and the owner's WO-054 Batch A
> decisions. This package is designed to bound a qualified Australian
> commercial/privacy technology lawyer's review. It does not authorise engagement,
> legal spend, infrastructure, provider activation, customer data or WO-045.

## 1. Review outcome requested

Core fixed-scope engagement:

1. review and finalise an Australian launch Privacy Policy for Oryntela; and
2. review and finalise Australian B2B SaaS Terms for Oryntela.

Price these optional deliverables separately where possible:

- data processing agreement (DPA);
- customer order form; and
- launch subprocessor schedule.

The adviser is asked to return publication-ready documents and a short list of any
remaining owner choices. No opinion is requested on inactive future features except
where their exclusion or future activation mechanism must be addressed in the launch
documents.

## 2. Confirmed business and owner decisions

| Item                                   | Confirmed fact or decision                                                                                                       |
| -------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------- |
| Product/business name                  | Oryntela                                                                                                                         |
| Proposed contracting/publishing entity | Management Services Australia Pty. Ltd.                                                                                          |
| ABN / ACN                              | ABN 15 113 119 556 / ACN 113 119 556                                                                                             |
| Public register status                 | ABN active and GST registered from 25 February 2005; [official ABN Lookup](https://abr.business.gov.au/ABN/View?abn=15113119556) |
| Initial market                         | Australia                                                                                                                        |
| Proposed canonical domain              | `https://oryntela.com.au`                                                                                                        |
| Privacy/support contact                | `support@oryntela.com.au`                                                                                                        |
| General contact                        | `hello@oryntela.com.au`                                                                                                          |
| GST presentation                       | Owner selected GST-inclusive subscription prices on 11 September 2026                                                            |
| Identity                               | Clerk Pro month-to-month selected for the intended paid profile; not subscribed or configured                                    |
| Primary/backup topology                | DigitalOcean Sydney plus AWS S3 Sydney backup proposed; A$220/month is a planning ceiling only and no purchase is authorised     |
| Paid-launch providers                  | Stripe and OpenAI selected; neither is configured, activated or authorised to incur spend                                        |
| OpenAI cost control                    | Future A$50/month alert-and-stop ceiling; no present spending authority                                                          |
| Disabled providers                     | Prospect, Microsoft 365, Google Workspace, HubSpot and Salesforce                                                                |
| Customer data                          | None                                                                                                                             |
| Privacy/Terms status                   | Qualified review required; current public routes remain non-indexed GAP pages                                                    |

The owner still needs to confirm the entity's registered/principal address and that
Management Services Australia Pty. Ltd. is both the contracting entity and the entity
whose privacy obligations the documents describe.

## 3. Current factual drafts supplied for review

The existing [WO-054 Privacy Notice and Terms inputs](wo-054-draft-privacy-and-terms.md)
are supplied as the current factual draft. They deliberately contain no invented
liability, indemnity, warranty, jurisdiction, refund, SLA or consumer-law language.
They are not approved for publication.

This package resolves the prior factual GST-presentation question and consolidates
the data, provider and commercial evidence a reviewer would otherwise need to collect
from the repository. If this package conflicts with an implementation document, the
adviser should raise the discrepancy rather than infer legal wording.

## 4. Intended launch profile

The intended paid launch is a supervised, Australia-first B2B Sales Brain profile:

- Oryntela Native CRM and sales workflows run on the modular web/API/worker platform;
- production identity uses Clerk organisations and verified server-side sessions;
- paid subscriptions use Stripe-hosted Checkout and customer portal;
- bounded OpenAI Meeting Intelligence, Next Best Action, Follow-up Email draft and
  AI Debrief are intended after separate privacy/configuration gates pass;
- a human reviews consequential outputs and actions; OpenAI receives no CRM-write,
  email-send or tool authority;
- Prospect and Microsoft, Google, HubSpot and Salesforce connectors remain disabled;
- recording, raw-audio transcription, live interaction intelligence, visual evidence,
  document/email evidence providers, automatic outreach and external CRM writes are
  not part of the initial profile; and
- no production customer data may be used until legal publication, infrastructure,
  authentication, recovery and WO-045 gates pass.

## 5. Privacy factual package

### 5.1 Factual data inventory

| Category                 | Data handled                                                                                                                                                                                                                           | Source and purpose                                                                  | Intended recipient/storage                                                            | Launch state                                                   |
| ------------------------ | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------- | -------------------------------------------------------------- |
| Public-site operations   | Request time, route, network/security and content-minimised error metadata; no marketing/ad tracker is implemented                                                                                                                     | Browser request; deliver and secure the site                                        | DigitalOcean platform/CDN and operational logs                                        | Proposed, not deployed                                         |
| Identity and membership  | Name, business email, provider user/organisation IDs, membership, role, invitation, session and security metadata                                                                                                                      | User/organisation and Clerk; authenticate, authorise and administer tenancy         | Clerk plus bounded references in PostgreSQL                                           | Intended; production Clerk absent                              |
| Business directory       | Companies, business contacts, roles, contact points and relationship provenance                                                                                                                                                        | Authorised user, reviewed CSV, optional connected system or later approved provider | Tenant-scoped PostgreSQL                                                              | Implemented; no customer data                                  |
| Sales work               | Opportunities, stages, tasks, pipeline history, targets, forecasts, manager views and analytics facts                                                                                                                                  | Authorised users and product workflows; operate the sales process                   | Tenant-scoped PostgreSQL                                                              | Implemented                                                    |
| Organisation context     | Selling profile, offerings, methodology and approved revisions                                                                                                                                                                         | Organisation administrators; constrain and explain product output                   | Tenant-scoped PostgreSQL                                                              | Implemented                                                    |
| Interaction evidence     | Meeting/interaction metadata, deliberately pasted notes or plain-text transcripts and participant references                                                                                                                           | Deliberate authorised user input; record and analyse sales interactions             | Tenant-scoped PostgreSQL; selected transcript sent to OpenAI only if approved         | Transcript path intended; capture/recording disabled           |
| AI artefacts             | Executive Summary, Decisions, Action Items, Risks & Blockers, Open Questions, Buying Signals, Objections & Competitive Signals, Stakeholder Intelligence, Next Best Action and Follow-up Email drafts; model/job/schema/usage metadata | OpenAI response to an explicit request; provide reviewable sales intelligence       | Validated tenant-scoped PostgreSQL artefacts; content-minimised telemetry             | Intended; OpenAI inactive                                      |
| AI Debrief               | Typed questions, answers, selected fragments, candidate evidence and review state                                                                                                                                                      | Deliberate user input; guide post-interaction review                                | Tenant-scoped PostgreSQL; bounded inputs to OpenAI if approved                        | Intended bounded text path; audio disabled                     |
| Actions and outreach     | Proposed action, destination, exact version, approval, expiry, suppression and outcome metadata; approved message body if a mailbox is later connected                                                                                 | User-created/reviewed workflow                                                      | PostgreSQL and selected customer provider only when separately enabled                | Internal/manual actions available; external providers disabled |
| Create and handover      | Presentations, business cases, source revisions, checksums, approvals, download grants and reviewed closed-won handover                                                                                                                | Authorised user and deterministic product generation                                | PostgreSQL and private object storage                                                 | Implemented; target storage absent                             |
| Deal Room                | Deliberately selected customer-facing fields, approved pinned presentation references, immutable publication revision, expiry/revocation state and token digest                                                                        | Seller reviews and publishes a bounded snapshot to a buyer                          | PostgreSQL/private object storage; buyer receives only allow-listed public projection | Implemented; production not deployed                           |
| Integration credentials  | Provider account IDs, scopes, connection/health state and encrypted delegated tokens                                                                                                                                                   | Customer-authorised OAuth connection                                                | Encrypted tenant-scoped token envelope; relevant provider                             | Optional and disabled                                          |
| Subscription billing     | Provider-mode account/customer mapping, plan/interval, subscription state, paid period, invoices, AUD amounts, provider tax total, hosted-link and reconciliation metadata                                                             | Stripe Checkout, portal and signed provider events                                  | Stripe plus tenant-scoped PostgreSQL projection                                       | Engineering complete; live Stripe inactive                     |
| Credits                  | Purchased/promotional balance, lots, quotes, reservations, immutable ledger, provider-cost metadata and manual paid-grant record                                                                                                       | Verified payment/test flow or protected cleared-funds operator exception            | Tenant-scoped PostgreSQL                                                              | Production packs/provider execution inactive                   |
| Support and feedback     | Sender identity, correspondence supplied by the sender, request/incident metadata and feedback                                                                                                                                         | Customer/user contacting Oryntela                                                   | Zoho Mail; minimum content-minimised operational records                              | Zoho active; customer use not approved                         |
| Audit, jobs and security | Opaque tenant/actor/resource IDs, lifecycle, timestamps, request/job/provider IDs, result, safe error codes, latency and token counts                                                                                                  | Application/provider operations; security, support and reconciliation               | Tenant-scoped PostgreSQL and content-minimised platform logs                          | Implemented in repository                                      |
| Export and backup        | Authorised organisation export plus encrypted PostgreSQL/private-object backup and authenticated content-free manifest                                                                                                                 | Tenant export request and daily recovery operation                                  | Private active storage; encrypted independent AWS S3 backup                           | Implementation exists; production targets absent               |

Oryntela is not designed to receive account passwords, authentication tokens in
content fields, payment-card numbers, government identifiers, medical/special-category
information or unrelated personal files. It never records or listens implicitly.

### 5.2 Customer-data flows

1. **Authentication:** browser → Clerk hosted identity/session → Oryntela web → API;
   the API verifies issuer, audience, signature, expiry, active organisation and
   current membership before resolving a tenant.
2. **Native sales data:** authorised browser → Oryntela API → tenant-predicated service
   and repository → forced-RLS PostgreSQL; approved private files go to tenant-scoped
   private object storage.
3. **OpenAI:** deliberate transcript/debrief request → API/worker minimisation and
   schema-bound prompt → OpenAI Responses API → strict validation → tenant-scoped AI
   artefact. No action, CRM write or email send follows automatically.
4. **Billing:** Oryntela server creates a Stripe-hosted Checkout/portal session → the
   customer supplies payment data directly to Stripe → signed Stripe event plus
   current-object retrieval → bounded Oryntela account/subscription/invoice projection.
5. **Deal Room:** authenticated seller reviews allow-listed draft → immutable snapshot
   and secret fragment link → buyer exchanges the secret in a no-store request →
   narrow public projection and any pinned approved presentation. Internal Opportunity
   data is not serialised to the buyer.
6. **Support:** person → Oryntela support/privacy address → Zoho Mail → minimum support
   or incident metadata where operational follow-up requires it.
7. **Recovery:** PostgreSQL/private objects → streaming AES-256-GCM encryption →
   independent private AWS S3 Sydney backup; encryption key remains separately
   controlled.
8. **Optional connectors:** there is presently no Microsoft, Google, HubSpot,
   Salesforce or Prospect customer-data flow. Each requires separate activation,
   customer authority, disclosure and proof.

The browser has no privileged direct database access. No customer data exists today.

### 5.3 Intended launch subprocessors/services

These are operational candidates, not counsel-approved legal descriptions. The final
schedule must identify each applicable contracting entity, current terms/DPA,
subprocessor-list URL, change mechanism and configured location.

| Service         | Purpose and data                                                                                                                        | Location fact                                                                                                                                                             | Current state                                                        |
| --------------- | --------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------- |
| DigitalOcean    | Sydney web/API/worker, managed PostgreSQL, private Spaces, platform logs/alerts; handles application records and active private objects | Data-plane target is Sydney; global edge, control plane, support and subprocessors prevent an exclusively Australian-processing claim                                     | Selected topology; no resource or spend                              |
| AWS S3 Standard | Independent encrypted database/object backup; encrypted payloads and content-free manifest, never the separate key                      | Bucket target is Sydney `ap-southeast-2`; control plane, billing, support and service metadata may be processed elsewhere                                                 | Selected backup; no account/bucket/spend                             |
| Clerk           | Identity, organisations, invitations, sessions, role claims and identity email/UI                                                       | No Australian-residency commitment identified; provider/subprocessor locations apply                                                                                      | Pro month-to-month selected; not subscribed/configured               |
| Zoho Mail       | General, support, privacy and incident correspondence                                                                                   | Exact contractual location/cross-border position still requires review                                                                                                    | Existing configured service; no customer data approved               |
| Stripe          | Hosted Checkout/portal, payment collection and subscription/invoice metadata                                                            | Stripe contractual/subprocessor locations apply; Oryntela does not receive raw card details                                                                               | Paid-launch provider selected; no live configuration/customer/charge |
| OpenAI          | Bounded transcript/debrief and validated-artefact processing described below                                                            | Global processing is the default proposal. Australian regional storage does not provide Australian regional inference processing and requires eligible retention controls | Paid-launch provider selected; no project/key/billing/request        |

### 5.4 Optional disabled and future providers

| Classification    | Provider          | Potential data if later activated                                                                                                  | Current fact                                                                                             |
| ----------------- | ----------------- | ---------------------------------------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------- |
| Optional disabled | Microsoft 365     | Connected identity, approved outbound Outlook mail, correlated reply content/metadata, basic calendar metadata and encrypted token | Adapter only; no app/account/mailbox/data/request                                                        |
| Optional disabled | Google Workspace  | Connected identity, approved Gmail mail, correlated reply content/metadata, calendar metadata and encrypted token                  | Adapter only; restricted-scope verification not performed                                                |
| Optional disabled | HubSpot           | Allow-listed company, contact, opportunity and reviewed writeback fields plus encrypted token                                      | Adapter only; no app/account/data/request                                                                |
| Optional disabled | Salesforce        | Allow-listed company, contact, opportunity and reviewed writeback fields plus encrypted token                                      | Adapter only; no app/org/data/request                                                                    |
| Future            | Prospect provider | Company/professional identity and research provenance after explicit seller action                                                 | No provider selected or licensed; Apollo adapter exists but required SaaS/data-sharing rights are absent |

Fly.io and Supabase were evaluated infrastructure alternatives and were not selected.
They should not appear as active launch subprocessors.

### 5.5 International-processing facts

- Sydney application/database/object/backup locations do not establish exclusively
  Australian processing.
- DigitalOcean and AWS control-plane, edge, billing, support and subprocessor activity
  may occur elsewhere under their agreements.
- Clerk, Zoho and Stripe require provider-specific cross-border review and disclosure.
- OpenAI API data is not used to train or improve models by default unless the API
  customer opts in. Standard Responses API abuse-monitoring logs may contain customer
  content and are retained for up to 30 days, subject to documented exceptions.
- The intended integration sends foreground Responses requests with `store=false`.
  That prevents ordinary stored Responses application state; it is not a Zero Data
  Retention promise and does not remove standard abuse-monitoring processing.
- OpenAI's Australian endpoint supports regional storage, not regional inference
  processing. OpenAI states customer content may be processed and temporarily stored
  outside a selected region that lacks regional processing, and non-US data residency
  requires approved abuse-monitoring controls and a retention amendment.

OpenAI facts were rechecked on 11 September 2026 against
[official OpenAI data controls](https://developers.openai.com/api/docs/guides/your-data)
and the [`store` parameter](https://developers.openai.com/api/reference/cli/resources/responses/methods/create).
The launch documents must not promise Australian-only processing.

### 5.6 Retention and deletion facts

| Item                                       | Implemented or proposed behaviour                                                                                                                                                                  | Decision still required                                                         |
| ------------------------------------------ | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------- |
| Ordinary retention-eligible tenant content | Organisation setting supports 30, 90 or 180 days, or manual; repository default is 90 days. Domain jobs affect eligible completed/cancelled resources, not every active canonical record at day 90 | Select and describe the launch setting; 90 days is recommended but not approved |
| Active canonical records                   | Remain until archive, offboarding/deletion or another documented lifecycle applies                                                                                                                 | Define customer-facing expectations                                             |
| Export                                     | Tenant-scoped export with authenticated one-time download grant expiring after 24 hours                                                                                                            | Approve request verification, format and availability wording                   |
| Organisation deletion                      | Operator-supervised disable/export/revoke/delete/reconcile workflow; production flag stays off until named-target proof                                                                            | Approve authority, exceptions, timing and evidence                              |
| Active private files                       | Deleted/reconciled through authorised file or organisation workflows                                                                                                                               | Approve applicable lifecycle wording                                            |
| Managed database recovery                  | DigitalOcean managed backup/PITR proposed                                                                                                                                                          | Confirm provider window after target creation                                   |
| Independent backup                         | Daily encrypted database/object bundle proposed; 14-day current/noncurrent/delete-marker lifecycle recommended                                                                                     | Approve 14 days and explain backup ageing rather than instant erasure           |
| Operational logs                           | Content-minimised; 14 days recommended                                                                                                                                                             | Approve exact period                                                            |
| Billing/Credit history                     | Append-only/restrictively retained; organisation deletion fails closed while unresolved history exists                                                                                             | Qualified accounting/legal retention and disposal period required               |
| Provider-held data                         | Governed separately by Clerk, Stripe, Zoho, OpenAI and any later provider                                                                                                                          | Approve provider disclosure and request limitations                             |
| Disabled capture paths                     | Live intelligence defaults and recording/audio lifecycles exist in code/docs, but these capabilities are excluded from launch                                                                      | Do not present them as active processing                                        |

No notice should promise immediate physical erasure from immutable backups or deletion
from an upstream customer-controlled system. Connector revocation and local deletion
are distinct from upstream deletion.

### 5.7 Security controls

Implemented in the repository:

- server-verified identity/organisation design with fail-closed production settings;
- explicit tenant predicates, transaction-local trusted tenant context and forced
  PostgreSQL RLS; the runtime role is designed as non-superuser/non-`BYPASSRLS`;
- composite tenant foreign keys for tenant-owned relationships;
- encrypted connector-token envelopes and server-only provider secrets;
- private object storage, resource-specific short-lived grants and bounded files;
- input/schema/provider-response validation and safe request-ID errors;
- content-minimised logs/audits that exclude credentials, authorisation headers,
  transcripts, prompts, customer documents and full provider payloads;
- durable job leases, idempotency, bounded retries and explicit unknown-outcome
  reconciliation;
- review/approval boundaries for external actions and provider-derived output; and
- AES-256-GCM logical database/object backup implementation with authenticated
  manifest and separate key custody.

Not yet established in a production environment:

- production Clerk configuration/MFA proof;
- actual DigitalOcean database roles, private storage and verified TLS;
- production secrets and rotation evidence;
- production monitoring/alert destinations;
- AWS lifecycle/freshness alert and independent recovery-key custody; and
- named-cloud backup/restore, deletion and cross-tenant production proof.

These are safeguards, not an absolute-security guarantee or contractual SLA.

### 5.8 Deal Room data model

- One tenant-scoped draft exists per Opportunity.
- Publication is deliberate and creates a complete immutable numbered snapshot from a
  positive public allow-list. Later internal edits do not alter the published snapshot.
- Approved Business Case/Create presentation sources are pinned to exact revisions.
- A high-entropy secret is shown once; only its SHA-256 digest is stored. The secret
  is carried in the browser URL fragment, removed from browser history and exchanged
  through a no-store POST.
- Optional expiry, pause, revocation and rotation are supported. Closed/archived
  Opportunities deny public access.
- Public access uses narrow database functions returning only the current public
  projection or one pinned presentation; anonymous access to tenant tables is absent.
- The buyer has no account, editing, comments, automatic email or view tracking.
- The owner/adviser must decide how customer responsibility for link recipients,
  authorised publication and confidential information is expressed.

### 5.9 Billing and Credits data model

**Billing**

- Stripe-hosted Checkout and portal keep card numbers/CVV outside Oryntela.
- The server, not the browser, selects the immutable plan, AUD amount, interval and
  provider Price.
- Oryntela stores mode-scoped account/subscription/invoice/operation/event projections,
  bounded amounts and provider-hosted links; webhook bodies and payment credentials
  are not stored.
- Access requires current provider state plus the latest verified paid invoice and a
  future paid-through boundary. Checkout success or the redirect alone is insufficient.
- Duplicate/stale events are idempotent; ambiguous outcomes fail closed for
  reconciliation.
- Live Stripe remains disabled until legal copy, policy reference, live account,
  prices, webhook, portal, preflight and separately authorised smoke all pass.

**Credits**

- Credits are integer units for deliberately metered variable-cost actions; they are
  not money, provider units, plan entitlement or permission to contact a person.
- Production packs, prices, margin floor, public purchase and provider execution do
  not exist. Current catalogue values are labelled TEST only.
- Tenant state uses separate purchased/promotional balances, lots, quotes,
  reservations, operations and an immutable ledger under forced RLS.
- The exceptional manual paid grant is internal CLI-only. It requires exact externally
  cleared funds, preview, balance-version check, stable idempotency, explicit
  confirmation and an immutable non-expiring purchased lot/ledger event. It does not
  create an invoice and cannot represent unpaid/pending funds as Credits.
- Refund, expiry, no-match/provider-failure, correction, pack and accounting treatment
  remain contractual/commercial decisions.

### 5.10 OpenAI intended launch data flow

| Feature                               | Sent to OpenAI                                                                                                              | Not sent by that path                                                        |
| ------------------------------------- | --------------------------------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------- |
| Eight Meeting Intelligence extractors | Registered instructions/strict schema plus the deliberately selected transcript, bounded to 50,000 characters per extractor | Credentials, auth headers, unrelated tenant records, files, audio and images |
| Next Best Action                      | Eight validated current-transcript artefacts                                                                                | Original transcript                                                          |
| Follow-up Email draft                 | Validated Executive Summary, Decisions, Action Items and Open Questions plus selected tone                                  | Original transcript and mailbox credentials; no email is sent                |
| AI Debrief                            | Bounded normalised context, typed answers or selected text fragments needed for the next question/evidence                  | Raw recording/audio in the launch profile                                    |

Names, employers, roles, business contact details, meeting statements, needs,
objections, decisions and actions may appear in authorised inputs. Responses are
foreground, strict-schema, `store=false`, no-tools and non-streaming. Oryntela stores
only validated output and content-minimised request/usage metadata. It grants OpenAI
no authority to mutate CRM records, send communications or act for the customer.

The proposed controls are one restricted project/key, no voluntary data-sharing
opt-in, 50 new generations and 75 OpenAI attempts per organisation/UTC day, an A$50
monthly alert-and-stop ceiling, weekly spend review and a tested kill switch. These
controls are not active and do not themselves establish customer authority or legal
compliance.

## 6. Terms factual package

### 6.1 Plans, prices and users

| Plan       |                                Monthly |     Annual prepayment | Included users | Product fact                                                                                               |
| ---------- | -------------------------------------: | --------------------: | -------------: | ---------------------------------------------------------------------------------------------------------- |
| Core       |                    A$200 including GST | A$2,000 including GST |        Up to 5 | Core operating loop, Native CRM and Pipeline                                                               |
| Growth     |                    A$350 including GST | A$3,500 including GST |       Up to 10 | Core plus Prospect and Engage entitlements; unavailable providers must remain visibly inactive             |
| Complete   |                    A$500 including GST | A$5,000 including GST |       Up to 15 | Growth plus Create and supported external CRM connector entitlements; provider activation remains separate |
| Enterprise | Custom; quote must state GST treatment |                Custom |     Contracted | No self-service Price or checkout                                                                          |

The price is per customer organisation/company with an included-user band, not a
per-user price. Extra-user bands/prices are undecided. Annual pricing is paid in
advance and represents approximately two months free relative to twelve monthly
payments; it is not a monthly instalment plan.

GST arithmetic for the fixed inclusive prices is:

| Price            | Customer total | Pre-GST amount | GST component |
| ---------------- | -------------: | -------------: | ------------: |
| Core monthly     |       A$200.00 |       A$181.82 |       A$18.18 |
| Core annual      |     A$2,000.00 |     A$1,818.18 |      A$181.82 |
| Growth monthly   |       A$350.00 |       A$318.18 |       A$31.82 |
| Growth annual    |     A$3,500.00 |     A$3,181.82 |      A$318.18 |
| Complete monthly |       A$500.00 |       A$454.55 |       A$45.45 |
| Complete annual  |     A$5,000.00 |     A$4,545.45 |      A$454.55 |

Amounts use decimal arithmetic at 10% and are rounded to cents. The adviser/accountant
should confirm tax-invoice, rounding, overseas-customer and accounting treatment; the
owner's commercial instruction is that the stated customer totals do not increase.

### 6.2 Trial policy

- One 14-day Complete trial per organisation.
- No card, charge or automatic conversion.
- Trial starts through a controlled operator action; self-service enrolment is not live.
- Trial expiry does not create a subscription or debt.
- Any grace/extension, trial eligibility representation and trial termination wording
  require commercial/legal confirmation.

### 6.3 Stripe subscription model

- Six server-owned self-service offers: Core/Growth/Complete, monthly/annual.
- Enterprise remains manual; no self-service Enterprise Price.
- Hosted Checkout/portal handles payment credentials.
- Verified current subscription plus latest paid invoice/paid-through controls paid
  access; trial or redirect state cannot grant it.
- Upgrades become authoritative only after provider confirmation; provider calculates
  proration.
- Lower-tier and same-tier interval changes take effect at the next renewal boundary.
- Cancellation is scheduled for period end and may be reversed before the boundary.
- `past_due` preserves current access/data while Stripe applies its configured recovery
  process; Oryntela does not invent a recovery duration.
- Verified terminal `unpaid`/`cancelled` ends paid functionality without deleting
  retained customer data. A later verified paid state can restore authority.
- Oryntela has no implemented general refund operation or approved refund policy.

### 6.4 Credits and manual paid exception

- Ordinary software and current subscription-funded AI are not charged in Credits.
- Future Credits cover deliberate operations with material third-party variable cost.
- No production packs, action prices, expiry policy, margin floor, auto-top-up or live
  purchase path is approved.
- A future normal purchase must be automatically granted only after verified payment.
- A genuinely large negotiated purchase may be invoiced externally. The protected
  manual path may grant non-expiring purchased Credits only after an authorised
  operator independently confirms exact cleared funds; it has no unpaid/pending state.
- The customer cannot self-grant. The operation is immutable/idempotent and does not
  fabricate a Stripe invoice or accounting fact.

### 6.5 Provider licences and availability

- Customers provide and maintain any required Microsoft 365, Google Workspace,
  HubSpot or Salesforce account, licence, API access, mailbox and tenant consent.
- Oryntela provider enablement remains separate and can be refused or withdrawn when
  security, licence, consent, cost or reliability gates fail.
- Stripe and OpenAI are intended for the paid launch but are presently inactive.
- Prospect has no selected/licensed provider. It must not be sold as operational.
- Microsoft, Google, HubSpot and Salesforce remain disabled and must be described as
  activation-dependent rather than immediately available.
- Provider downtime, terms, limits, data locations and customer-account changes can
  affect availability; responsibility allocation requires counsel.

### 6.6 AI and review-first boundaries

- AI output is evidence-bounded, schema-validated, reviewable and potentially
  incomplete or inaccurate.
- OpenAI has no implicit tools, credentials, CRM-write or email-send authority.
- Follow-up content is a draft. Consequential external communications and CRM writes
  require valid human review/approval and an enabled customer connection.
- Oryntela does not provide legal, financial or other professional advice and is not
  an autonomous decision-maker.
- Users remain responsible for input authority, output review, recipient rights,
  sending rules and decisions made using the service.
- Users must not supply credentials, payment-card data, unlawful content,
  special-category data or content they lack authority to use. The service does not
  authorise unsolicited bulk marketing.

## 7. Exact unresolved legal and contractual questions

The following **24 questions** require qualified advice and/or explicit owner
approval. They are not answered by engineering.

### Privacy and data protection

1. Does the Privacy Act 1988 (Cth), including the APPs and any small-business
   exceptions/limitations, apply to this entity and launch profile, and what entity
   identification, notices and governance are required?
2. Is Management Services Australia Pty. Ltd. the correct contracting and privacy
   entity, and what registered/principal address and contact details must appear?
3. How should Oryntela's and each customer's privacy roles and instructions be
   characterised, and is a DPA required or commercially advisable?
4. What collection notices, purposes and authority representations are required for
   business contacts, employees, meeting participants, transcripts, CSV imports and
   customer-entered content?
5. What customer warranties, consents or administrative controls are needed before
   connecting mailbox, calendar or CRM data, performing reviewed writeback or sending
   communications?
6. What disclosures/authority are required for the bounded OpenAI data flow, including
   names and meeting content, standard abuse-monitoring retention and human review?
7. How should international processing and overseas disclosure be expressed for
   DigitalOcean, AWS, Clerk, Zoho, Stripe and OpenAI, and are further transfer terms or
   diligence required?
8. Which providers must be named at launch, what subprocessor-change notice/objection
   mechanism is appropriate, and should disabled/future providers be omitted entirely?
9. What exact application, log, backup, provider, billing and Credit retention periods
   and lawful exceptions should apply, including accounting/legal-hold requirements?
10. What deletion/export commitments can be made accurately across active systems,
    customer-controlled upstream systems, providers and ageing encrypted backups?
11. What access, correction, complaint, authority-verification, response-time and
    regulator-escalation procedure should the Privacy Policy promise?
12. What suspected-breach assessment, notification, customer communication and
    incident-record obligations must the operational plan and customer documents use?

### Terms and commercial contract

13. What clickwrap/order-form acceptance and representative authority mechanism is
    sufficient, and which document prevails on conflict?
14. What subscription term, automatic renewal, annual prepayment, cancellation,
    price-change and notice wording should apply?
15. What failed-payment, retry, grace, suspension and restoration rules should apply
    without contradicting Stripe-confirmed authority or the implemented `past_due`
    behaviour?
16. What refund/cancellation policy is commercially appropriate and compliant with
    non-excludable Australian Consumer Law rights?
17. What Credit purchase, expiry, refund, no-match, provider-error, price-change and
    manual cleared-funds terms are required before production Credits can be sold?
18. How should customer-data ownership, Oryntela's processing licence, confidentiality,
    feedback, derived output, export and post-termination rights be allocated?
19. How should customer-provided provider licences, consent, limits, downtime,
    deprecation and unavailable optional capabilities be allocated and disclosed?
20. What AI-output accuracy, human-review, prohibited-use and no-professional-advice
    clauses are appropriate without overstating performance or excluding mandatory law?
21. What warranties, disclaimers and non-excludable consumer guarantees apply to this
    B2B SaaS and trial profile?
22. What liability cap/exclusions, indemnities and insurance-related provisions are
    appropriate and enforceable for the actual risk profile?
23. What termination, suspension, offboarding, data-retrieval, deletion, survival,
    governing-law, jurisdiction, dispute, notice, assignment and force-majeure terms
    should apply?
24. What support hours, response commitments, maintenance/change rights and service
    levels—if any—should be contractual, and which DPA, order-form and subprocessor
    schedule deliverables are required for the first paid customer?

## 8. Proposed fixed-scope adviser request

Ask an Australian commercial/privacy technology lawyer to:

- validate the factual package against applicable Australian law;
- finalise one launch Privacy Policy and one B2B SaaS Terms document;
- identify only decisions that cannot be completed without owner input;
- preserve the documented product/provider limitations and GST-inclusive totals;
- avoid drafting future inactive capabilities as current services; and
- separately quote the DPA, order form and subprocessor schedule.

Request a fixed or capped GST-inclusive fee, turnaround, included revision rounds,
exact deliverables/editable formats, assumptions/exclusions and any missing factual
inputs. No engagement or deposit is authorised by the request.

## 9. Draft quote email — not sent

**Subject:** Fixed-fee quote request — Oryntela Privacy Policy and B2B SaaS Terms

Dear [Lawyer/firm name],

I am seeking a fixed or capped-fee quote for a tightly scoped Australian technology
law review for Oryntela, an Australia-first B2B SaaS sales-work platform operated by
Management Services Australia Pty. Ltd. (ABN 15 113 119 556).

The core engagement requested is:

1. review and finalisation of a launch Privacy Policy; and
2. review and finalisation of B2B SaaS Terms.

Please price the following optional deliverables separately where possible:

- a data processing agreement;
- a customer order form; and
- a launch subprocessor schedule.

To minimise discovery time, I have prepared a factual review package covering the
actual product boundary, data inventory and flows, intended and disabled providers,
international-processing facts, retention/deletion behaviour, implemented security
controls, Deal Room, Stripe billing, Credits, OpenAI processing, subscription plans,
GST-inclusive pricing, trial policy and a bounded list of unresolved legal questions.
There is currently no customer data and no production infrastructure or live provider
configuration.

The initial paid profile is intended to use DigitalOcean Sydney, an independent AWS
S3 Sydney encrypted backup, Clerk, Zoho Mail, Stripe and bounded OpenAI processing.
Prospect, Microsoft 365, Google Workspace, HubSpot and Salesforce will remain disabled
at launch. Consequential actions are review-first; Oryntela is not an autonomous
decision-maker or professional-advice service.

Could you please provide:

- a fixed or capped fee, stated as a GST-inclusive total, for the two core documents;
- separate GST-inclusive prices for each optional deliverable;
- expected turnaround from receipt of the factual package;
- the number of included revision rounds;
- the exact deliverables and editable file formats;
- assumptions, exclusions and the rate/cap for any work outside scope; and
- any additional factual information required before you can finalise the documents?

Please treat this as a quote request only. It does not authorise engagement, a deposit
or commencement of work. I will provide written approval separately if I decide to
proceed.

Kind regards,

Kevin Finnerty<br>
[Role]<br>
Management Services Australia Pty. Ltd.<br>
Oryntela<br>
`hello@oryntela.com.au`

## 10. Package status and exclusions

| Item                       | Status                                                                       |
| -------------------------- | ---------------------------------------------------------------------------- |
| Privacy factual package    | Ready for qualified review; not approved public copy                         |
| Terms factual package      | Ready for qualified review; not approved contract                            |
| Data inventory             | Ready for qualified review                                                   |
| Subprocessor schedule      | Factual candidate ready; exact entities/terms and legal approval outstanding |
| OpenAI data flow           | Ready for qualified review; no activation authority                          |
| Unresolved legal questions | 24                                                                           |
| Quote email                | Drafted; not sent                                                            |
| Professional contact       | None                                                                         |
| Legal spend                | A$0                                                                          |
| Production spend           | A$0                                                                          |
| Production activation      | Not started                                                                  |
| WO-045                     | Not started                                                                  |
