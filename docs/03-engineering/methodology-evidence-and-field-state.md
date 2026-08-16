# Methodology Evidence and field states

Methodology state is an evidence classification, not confidence, probability or a
performance score.

| State | Rule | User meaning |
| --- | --- | --- |
| `confirmed` | Current admissible customer-direct/accepted support satisfies the field | RevenueOS has current Evidence and shows why |
| `partially_supported` | Credible support exists but identity, detail or authority is incomplete, or support is seller-reported/contextual | Some of the answer is known; a material gap remains |
| `unknown` | No reliable current admissible support | Absence is not a negative fact; ask the natural gap question |
| `conflicting` | Current admissible sources materially disagree | Both sides remain visible for review |
| `stale` | Previously admissible support exceeds that field's policy | Revalidate; history remains intact |

Every supported item carries source type, source ID, bounded item key and label,
origin classification, support classification and supported timestamp. Conflict
references are separate. The product displays plain provenance labels on demand and
does not expose internal fingerprints, prompts or provider fields.

User actions are immutable reviews: confirm the interpretation, mark not known, mark
incorrect, or clarify. A clarification that adds information creates a new verified
`salesperson_reported` Evidence row linked back to the review. It never edits the
original Evidence and never becomes `customer_direct` because of a click. A refresh
is then required so source fingerprinting and field policy are reapplied.

Supported source classes in v1 are final AI artefacts, accepted documentary/email
findings, final Interaction Intelligence, safe Opportunity metadata and review
clarification Evidence. Provisional live output and raw customer content are outside
this boundary.
