# RevenueOS Native CRM

- **Status:** WO-034 foundation, WO-035 Native Pipeline and WO-039C supervised import/merge implemented
- **Promise:** Small teams can run their sales CRM and Sales Brain in one place; larger teams can keep HubSpot and use the same RevenueOS intelligence layer.

## What customers get

Company, Contact and Opportunity records now form a deliberately simple sales CRM. Sellers can create and edit short records, assign an owner, prevent strong duplicates, view recent relationship activity and inspect field history. Entitled administrators can archive/restore records, choose RevenueOS as system of record and administer up to 25 active custom fields for each record type.

RevenueOS remains Sales Brain with an optional CRM, not a generic CRM with an AI tab. Interactions, Evidence, Methodology, Revenue Brain, Actions, Daily, Prospect, Engage and Create continue to own their existing concepts. CRM reads them; it does not duplicate them.

## Modes

| Mode         | System of record            | Editing behaviour                                                                                                |
| ------------ | --------------------------- | ---------------------------------------------------------------------------------------------------------------- |
| RevenueOS    | RevenueOS canonical records | Normal and bounded custom fields editable under Core role/tenant policy                                           |
| External CRM | HubSpot in v1               | Mapped authority is shown; HubSpot-authoritative fields are read-only; review-before-sync behaviour is preserved |

An administrator makes and confirms the choice in Settings → CRM. HubSpot must be connected before selecting external mode. Active field mappings must be resolved before switching to native mode; WO-034 does not pretend to be a migration wizard.

## Packaging

Core includes the Accounts, People and Opportunity records needed by Sales Brain,
Native CRM system-of-record configuration, bounded custom fields, archive/restore,
canonical activity/history and configurable Pipeline. Under WO-047 the CRM commercial
module means supported external CRM connectors. Removing that connector entitlement
preserves external history but blocks new connection/sync actions; it does not remove
Native CRM from Core.

WO-047 adds plan and trial authority; WO-048 adds test billing/payment operations only. Plan
and connector access is support-operator managed, not an organisation-admin switch.

## Record experience

- **Account:** name, website/domain, industry, location, employee count, minimal relationship status and owner.
- **Contact:** name, Company, role, optional business email/phone, LinkedIn URL, owner and `active`/`left_company` employment status.
- **Opportunity:** Account, name, existing stage/status, decimal amount, currency, expected close, description and owner.

Lists stay card-like and bounded rather than becoming forty-column spreadsheets. Search continues across Accounts, Contacts, Opportunities and Interactions. Workspaces lead with relationship/deal context; core CRM fields are compact and custom fields are secondary. No manual “next step” field duplicates the current Action/Next Best Action.

## Trust and reduced data entry

Exact Company domain and Contact business email prevent strong duplicates within an organisation. Name similarity does not merge records. Prospect and Event promotion create the same canonical records and leave labelled history; Contact field-source provenance is preserved. External mappings continue to express source authority separately from whether a value is customer-confirmed evidence.

The intended long-term loop is Interaction → Evidence → Sales Brain → reviewed field update. WO-034 records the architecture but deliberately does not add local Action execution: no AI or approved proposal automatically changes a CRM record in this release.

## Data portability

Organisation export version 29 includes CRM settings, custom definitions, typed values,
record history, Pipeline definitions/current assignment/stage history, closure metadata
and content-free import/merge history alongside canonical records. WO-039C adds
admin-only explicit-map CSV preview/confirm for Accounts, Contacts and open
Opportunities. Raw CSV is not retained, formula-leading text is never executed,
duplicates are conservative and importing a Contact never grants Engage permission.
It also adds one-at-a-time reviewed Account/Contact merge with immutable tombstones,
provenance protection and most-restrictive suppression. See the
[import and merge architecture](../03-engineering/native-crm-import-and-merge.md).

## Opinionated limits

There is no Lead object or conversion ceremony; pre-sales discovery remains Prospect
and promotion creates a Company/Contact. There are no CRM-specific Tasks, Notes or
Activities, custom objects, formulas, rollups, workflows, page builders, mass edits,
automatic/fuzzy/batch merge, Opportunity merge, service desk, marketing automation, CPQ, team ownership or territory
routing. WO-035 now supplies bounded Pipeline/stage administration; WO-036 owns
analytics, implemented WO-037 targets, WO-038 forecasting and WO-039 manager intelligence.

## WO-035 Pipeline boundary

Core retains the descriptive Board/List/Closed experience and canonical stage history.
The CRM add-on unlocks native multiple-pipeline/stage administration. Native mode makes
RevenueOS authoritative; external mode shows `Managed in HubSpot` and denies direct
native movement. See the [implementation guide](native-pipeline.md) and
[packaging decision](pipeline-packaging.md).
