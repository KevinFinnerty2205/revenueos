# Sales Methodology UX

**Location:** Opportunity → Deal and Settings → Sales Methodology. There is no
top-level Methodology navigation item.

The Opportunity card first explains that the selected framework organises validated
Evidence without scoring or blocking stages. It shows categorical counts and the
three most important gaps, ordered conflict, stale, unknown, partial, then confirmed.
**View all** reveals the rest. Each field answers what RevenueOS believes, what to do
next and when it was supported. **Why this state** progressively reveals sources and
provenance. History loads only on request.

Review controls use plain actions: Confirm interpretation, Add clarification, Mark
not known and Mark incorrect. Clarification explicitly warns that it is
salesperson-reported and not customer-confirmed. Changed sources hide old current
conclusions until Refresh evidence succeeds. Empty/error states explain the next
action; `none` leaves the rest of RevenueOS fully usable.

On narrow screens the same semantic sequence naturally becomes one column: name and
summary, priority gaps, then View all. There is no dense matrix. Buttons remain touch
targets; state is text as well as colour; headings, lists, fieldsets, labels, alerts,
statuses and native details/summary controls support keyboard and screen-reader use.

Settings presents standard/default choices first and the advanced custom builder
below. Standard fields can be inspected without editing. Archiving is explicit and
preserves history. Salespeople never need to understand “projection”, canonical
facts or source fingerprints to complete the workflow.

## Simplicity review

- the most important gap is the first field, with a natural question;
- evidence is available but hidden until requested;
- no manual checklist or data re-entry is required;
- mobile is a simpler single-column disclosure;
- the feature can be ignored when the organisation selects none; and
- no score, stage gate, rep ranking or surveillance language appears.
