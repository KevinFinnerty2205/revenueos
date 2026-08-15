# Document and email provenance

## Two independent facts

WO-019 never conflates who supplied a source with who interpreted it:

| Source case | Origin class | Support class | Interpretation origin |
| --- | --- | --- | --- |
| Customer-provided document | `customer_direct` | `direct` | `ai_inferred` until human review |
| Seller-provided document | `seller_prepared` | `context` | `ai_inferred` until human review |
| Jointly created document | `imported_external` | `reported` | `ai_inferred` until human review |
| Other/unknown document | `imported_external` | `context` | `ai_inferred` until human review |
| Verified inbound customer email | `customer_direct` | `direct` | `ai_inferred` until human review |
| Outbound or internal email | `salesperson_reported` | `context` | `ai_inferred` until human review |
| Manual/unknown sender email | `imported_external` | `reported` | `ai_inferred` until human review |

Human acceptance changes validation from unreviewed to verified; it does not change
the source origin. A seller proposal therefore remains seller-prepared context even
after a user accepts an extracted implementation detail.

## Traceability

Every candidate references its source Evidence row and either a document fragment
with page/paragraph or an email message paragraph. The candidate preserves the original
statement, any human-edited statement, source classification, review decision,
reviewer, time and optional superseded candidate. Accepted candidates receive a
new immutable Evidence ID. Revenue Brain snapshots reference only these accepted
IDs and copy the source label, type, date, location and provenance needed for a
safe timeline.

Normal application review cannot be reopened and source snapshots cannot be
updated. Replacement evidence is additive and links to the earlier accepted
candidate through `supersedes_candidate_id`; history is not silently overwritten.
If the earlier source is deleted, the later finding stays valid but its obsolete
database link is cleared; its immutable reviewed snapshot still records that it
superseded evidence available at review time.

## Downstream rules

Unreviewed, rejected, failed or deleted sources are absent from Opportunity
Workspace and Revenue Brain source APIs. Accepted source evidence augments the
timeline; it does not directly mutate CRM-style opportunity fields, declare a
contract binding, create a Contact or trigger an automated action.

Source deletion removes accepted evidence and its source snapshots, so deleted
content cannot remain eligible downstream. Export and retention preserve or remove
the same lineage as a unit.
