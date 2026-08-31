# Customer-facing terminology

Use these names in ordinary seller and manager experiences.

| Use | Meaning | Avoid in primary seller UI |
| --- | --- | --- |
| Account | The canonical Company record used for selling | Company object, CRM entity, source mode |
| Contact | A promoted business Person attached to an Account | Person object, contact entity |
| Opportunity | The canonical deal and centre of Sales Brain | Deal object, workspace object |
| Interaction | A planned or completed customer conversation | Meeting domain record, capture entity |
| Evidence | A source-labelled item accepted by a user | Artefact, fragment, inference object |
| Revenue Brain | Reviewed Account and relationship intelligence over time | Snapshot store, reasoning projection |
| Sales Brain | Opportunity-centred deal understanding and next work | Scoring engine, opportunity intelligence service |
| Methodology | Reviewed qualification fields and gaps | Projection engine |
| Action | Reviewed next work; approval and completion are explicit | Action proposal object |
| Pipeline | Open and closed Opportunities by stage | Stage-state service |
| Actual | Completed canonical activity or Won revenue | Observed aggregate |
| Target | A goal compared with Actual | KPI row |
| Forecast | Seller range plus a separately labelled historical baseline | AI prediction, weighted-pipeline truth |
| Manager view | Admin-only deal review and coaching context | Admin intelligence module |

“Provider supplied” is valid only when field provenance actually comes from a
provider. “RevenueOS record” is the customer-facing description for a canonical
record when an external CRM is not configured. Search finds records. Ask RevenueOS
answers only its displayed set of bounded, authorised questions.

Engineering vocabulary remains appropriate in admin documentation and diagnostic
logs that exclude customer content. It does not belong in routine seller headings,
empty states or recovery messages.
