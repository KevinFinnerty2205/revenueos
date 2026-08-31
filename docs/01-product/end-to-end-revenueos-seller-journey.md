# End-to-end RevenueOS seller journey

## Current journey

RevenueOS supports one connected, review-led seller loop. A seller starts at Home,
uses Find to research a previously unknown Company and Person, then deliberately
promotes them into the canonical Account and Contact records. From the Contact the
seller prepares and reviews Outreach, uses the simulation-only execution path, and
opens an Interaction.

The Interaction stays organised as **Prepare → Capture → Review → Follow through**.
Only user-accepted candidate Evidence updates Revenue Brain and Methodology. The
seller can then review an Action, create or open the canonical Opportunity, move it
through Pipeline, prepare an approved Business Case or presentation in Create, and
review Analytics, Target and Forecast context. An organisation admin can use the
Manager view to review the same Opportunity and ask bounded coaching questions.
Closing the Opportunity Won updates Pipeline, Actual, Target progress, Analytics and
Forecast eligibility while retaining stage, closure and forecast history.

## Canonical hand-offs

| From | To | Continuity rule |
| --- | --- | --- |
| Prospect Company | Account | Promotion returns the canonical Company ID; repeat promotion reuses it. |
| Prospect Person | Contact | Company must exist first; reviewed business fields and their provenance are retained. |
| Contact | Outreach | Outreach remains attached to the same Contact and Account. |
| Outreach | Interaction | Execution remains an explicit safe simulation; it does not claim delivery. |
| Interaction | Evidence | Candidate statements are deduplicated and require individual user review. |
| Evidence | Revenue Brain and Methodology | Only accepted Evidence becomes durable intelligence. |
| Account/Contact | Opportunity | Relationships use canonical IDs, never duplicate display-name records. |
| Opportunity | Pipeline, Create and Insights | Stage, close and reopen mutations trigger deliberate revalidation. |
| Closed Opportunity | Actual, Target, Analytics and Forecast | Won value becomes Actual/Target progress; the deal leaves open Forecast while history remains. |

## Product boundaries

RevenueOS is not a generic chat tool or a replacement for every CRM. Search finds
records; Ask RevenueOS answers a bounded set of authorised sales-data questions.
Prospect research is not customer Evidence. Revenue Brain is the durable reviewed
intelligence layer, and Sales Brain remains centred on the Opportunity.

This journey uses synthetic data in automated and documented demonstrations. It does
not authorise production customer data, live mailbox delivery, provider activation,
automatic recording, autonomous evidence acceptance or automatic CRM mutation.

## Related contracts

- [Journey reliability contract](journey-reliability-contract.md)
- [Customer-facing terminology](customer-facing-terminology.md)
- [Journey architecture](../03-engineering/journey-reliability-architecture.md)
- [WO-039A record](../07-sprints/wo-039a-end-to-end-journey-reliability.md)
