# Oryntela marketing claim inventory

- **Work order:** WO-053
- **Status:** Reviewed website claim authority; engineering review passed
- **Purpose:** Prevent public copy from outrunning the actual product

Every major marketed feature below has an implemented source. A target blueprint,
future roadmap entry or inactive provider does not independently authorise a public
“available” claim.

## Category, audience and core promise

| Public claim                         | Website treatment          | Product authority                                                                                       | Status/limit                                                        |
| ------------------------------------ | -------------------------- | ------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------- |
| End-to-end sales platform            | Primary category           | Completed WO-023–044 product baseline and [master blueprint](oryntela-master-product-blueprint.md)      | Implemented product breadth; production activation remains separate |
| Sales operating system               | Secondary category         | [Product principles](oryntela-product-principles.md) and completed cross-module workflow                | Category descriptor, not a new product                              |
| One system from prospect to handover | Hero headline              | Prospect, Engage, Create, Native CRM, Pipeline/Forecast/Analytics, Deal Room and Handover records below | Does not claim autonomous execution or every future sales function  |
| Australian B2B teams                 | Audience and AUD treatment | Owner-authorised WO-053 market; [personas](personas-and-jobs.md)                                        | No Australian certification, residency or cliché claim              |
| Know what deserves attention next    | Sales Brain outcome        | WO-025 Daily, WO-039 Manager Intelligence and existing reviewed Action/Sales Brain capabilities         | Suggestion/review support; no autonomous decision authority         |

## Product claims

| Feature                   | Public wording boundary                                                                                                                      | Implemented authority                                                                                                          | Prohibited extension                                                                               |
| ------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------ | -------------------------------------------------------------------------------------------------- |
| Sales Brain               | Understand what is happening and what deserves attention next; suggestions remain reviewable                                                 | [Oryntela Daily](../03-engineering/revenueos-daily-implementation.md), [Manager Intelligence](manager-intelligence.md), WO-021 | Autonomous decision maker, invisible customer-truth mutation                                       |
| Prospect                  | Define target markets; research potential accounts/contacts; inspect sources; explicitly promote records                                     | WO-026–028, WO-050, [Prospect provider architecture](../03-engineering/live-prospect-provider.md)                              | Live provider availability; unrestricted scraping; hidden provider success                         |
| Engage                    | Prepare/review individual outreach and small campaigns using connected business-mailbox context                                              | WO-029/030, WO-040/041 and [personalised outreach](personalised-outreach.md)                                                   | Autonomous spam, unrestricted bulk sending, production mailbox active                              |
| Create                    | Create customer-ready presentations from approved sources; review claims; download editable PowerPoint                                       | WO-032/039B and [Create](revenueos-create.md)                                                                                  | Arbitrary file product, automatic fact authority, error-free compatibility guarantee               |
| Business Cases            | Approved assumptions, deterministic maths, scenarios and sensitivity                                                                         | WO-033 and [ROI & Business Case Builder](roi-business-case-builder.md)                                                         | AI-invented numbers, CPQ, tax/FX/NPV automation                                                    |
| Oryntela CRM              | Native companies, people, opportunities, bounded fields/history and configurable Pipeline                                                    | WO-034/035/039C and [Native CRM](native-crm.md)                                                                                | Generic enterprise CRM replacement, marketing/service automation, arbitrary workflow builder       |
| Opportunity Workspace     | Commercial record, relationship activity, methodology, evidence, reviewed actions and history together                                       | WO-007 plus [Opportunity Workspace architecture](../03-engineering/opportunity-workspace.md)                                   | Every external record is current; automatic truth from unreviewed sources                          |
| Pipeline                  | Open opportunities by stage, owner and attention state with next actions visible                                                             | WO-035 and [Native Pipeline](native-pipeline.md)                                                                               | Stage as forecast probability or customer Evidence                                                 |
| Forecast                  | Explicit human Commit/Likely/Possible/Not this period judgement and immutable history                                                        | WO-038 and [Transparent Forecasting](transparent-forecasting.md)                                                               | Blended/final forecast, automatic probability, guaranteed accuracy                                 |
| Targets                   | Personal/organisation goals compared with canonical actuals                                                                                  | WO-037 and [Sales Targets](sales-targets.md)                                                                                   | Compensation, payroll, ranking or invented actuals                                                 |
| Analytics                 | Deterministic pipeline, activity and outcome views with clear definitions and separate currencies                                            | WO-036 and [Sales Analytics](sales-analytics.md)                                                                               | Predictive performance claim, fabricated benchmark, mixed-currency total                           |
| Manager Intelligence      | Deal attention, plain reasons, source links, discussion questions and independent manager judgement; evaluates opportunities, not people     | WO-039 and [Manager Intelligence](manager-intelligence.md)                                                                     | Employee score, ranking, surveillance, sentiment or automated manager forecast                     |
| Deal Room                 | Read-only buyer space with deliberately published overview, stakeholders, milestones, approved Business Case/presentation or HTTPS resources | WO-043 and [Deal Room architecture](../03-engineering/opportunity-deal-room.md)                                                | Buyer editing/comments/accounts, general files, e-signature, payment, analytics or automatic email |
| Closed-Won Handover       | Source-pinned internal package with review, administrator approval and immutable revisions                                                   | WO-044 and [Handover architecture](../03-engineering/closed-won-handover.md)                                                   | Automated implementation execution, Customer Success product, external system write-back           |
| Reviewed external actions | Preview, confirmation, idempotency and reconciliation are explicit where implemented                                                         | WO-021/022/025C/040–042 and [integration foundation](integrations-execution-foundation.md)                                     | Unsupervised external execution or certain success when provider outcome is unknown                |

## Commercial claims

| Claim      | Exact public value                                                                | Authority                                                    |
| ---------- | --------------------------------------------------------------------------------- | ------------------------------------------------------------ |
| Core       | AUD $200/month; AUD $2,000/year annual prepayment; 5 users                        | WO-047 `PLAN_CATALOGUE`; owner-authorised WO-053 publication |
| Growth     | AUD $350/month; AUD $3,500/year annual prepayment; 10 users                       | Same                                                         |
| Complete   | AUD $500/month; AUD $5,000/year annual prepayment; 15 users                       | Same                                                         |
| Enterprise | Custom                                                                            | Same                                                         |
| Trial      | 14 days; Complete-level modules; no card; no automatic charge; no auto-conversion | WO-047 contract/service plus owner-authorised WO-053 copy    |
| Credits    | Some eligible variable-cost research actions use Credits; no pack/price table     | WO-049/050; production packs/prices absent                   |
| Checkout   | No live checkout claim; trial/demo requests go to direct contact                  | WO-048 remains test mode; live Stripe is outside WO-053      |

The automated marketing test compares public plan tuples with the canonical Python
catalogue and checks the shared browser trial literals.

## Integration claims

| Integration      | Public status wording          | Implemented source                                                                            | Production state               |
| ---------------- | ------------------------------ | --------------------------------------------------------------------------------------------- | ------------------------------ |
| Microsoft 365    | Built · activation pending     | WO-040 and [Microsoft architecture](../03-engineering/microsoft-365-sales-integration.md)     | Not production-active          |
| Google Workspace | Built · activation pending     | WO-041 and [Google architecture](../03-engineering/google-workspace-sales-integration.md)     | Not production-active          |
| HubSpot          | Built · activation pending     | WO-042 and [CRM connector architecture](../03-engineering/production-crm-connectors.md)       | Not production-active          |
| Salesforce       | Built · activation pending     | WO-042 and [CRM connector architecture](../03-engineering/production-crm-connectors.md)       | Not production-active          |
| Apollo           | Not named publicly             | WO-050 implementation exists, but provider/commercial/privacy/production activation is absent | Not production-active          |
| Oryntela CRM     | Native system-of-record option | WO-034/035/039C                                                                               | Implemented product capability |

Public copy must not change to “live”, “connect now”, “available to all users” or an
equivalent until WO-054 records exact production activation evidence.

## Trust claims

| Public trust statement          | Implemented basis                                                                 | Limit shown publicly                                             |
| ------------------------------- | --------------------------------------------------------------------------------- | ---------------------------------------------------------------- |
| Explicit organisation isolation | Auth-derived tenant, explicit predicates, forced PostgreSQL RLS                   | No certification claim                                           |
| Role-aware access               | Current member/admin policies and fail-closed route/API behaviour                 | No enterprise SSO/SCIM claim                                     |
| Encrypted connector credentials | AES-256-GCM envelope implementation for production-capable connectors             | No general target-environment encryption/residency promise       |
| Reviewed consequential actions  | Review/approval lifecycle across Action, outbound, CRM, Deal Room and Handover    | No autonomous-execution claim                                    |
| Buyer-safe Deal Room            | Hash-only token storage, immutable allow-listed projection, pause/revoke, noindex | No buyer account/edit/e-signature/file-store claim               |
| Export/deletion workflows exist | Versioned organisation export and reviewed deletion implementation                | Production retention/backup/provider policy still needs approval |

No SOC 2, ISO 27001, PCI, HIPAA, government certification, penetration-test,
availability, customer-count, review, testimonial, performance uplift or revenue
uplift claim appears on the website.

## Legal and contact claims

- Oryntela is the product brand and registered business name.
- Management Services Australia Pty. Ltd., ABN 15 113 119 556, is the confirmed
  operator/holder fact authorised for the footer and Contact page.
- `hello@oryntela.com.au` and `support@oryntela.com.au` are approved and
  routing-tested.
- No registered-trade-mark symbol, legal-clearance claim or founder biography is
  published.
- Privacy and Terms are **GAP**, visibly identified as not yet approved and noindex.
