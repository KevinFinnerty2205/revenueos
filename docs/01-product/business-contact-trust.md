# Business Contact Trust guide

Business contact availability is separate from identity, accuracy and permission to contact.

WO-027 stores each permitted business contact point with type, value, source, trust state, verification method, observation time, optional expiry and export permission. The UI uses exact labels: **Verified**, **From data provider**, **RevenueOS inference** and **Not established**. It always states **Permission not assessed**.

V1 accepts a business email only when an approved source or provider supplies it. Inferred or pattern-generated email addresses are rejected rather than displayed. Personal emails, personal mobiles and direct-dial phone data are unsupported. Unknown is a valid result.

On promotion, Contact field provenance preserves the source trust. A provider-supplied email remains provider-supplied and does not become verified. Later Prospect refresh never silently overwrites the canonical Contact. If a provider-derived value expires and still matches the Contact field, maintenance removes that field and deactivates its provenance while preserving the Contact itself.

No outreach, sequence, campaign or sending capability is part of this work order. A seller remains responsible for lawful purpose, consent, suppression and channel rules in any future Engage workflow.
