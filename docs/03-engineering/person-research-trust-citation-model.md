# Person research trust and citation model

Person research uses the existing Prospect source and observation model. Every material current-role, background, activity, public-statement or rapport-context claim links to one or more sources from the same run. Buying-role hypotheses have their own many-to-many source links. Contact points reference one exact source.

Trust meanings are unchanged:

- `verified`: directly supported by an authoritative permitted public source or documented provider verification semantics;
- `provider_supplied`: reported by the configured business-data provider without independent verification;
- `inferred`: a cautious RevenueOS interpretation of cited public facts;
- `unknown`: not established; no value is guessed.

Sources store safe metadata, authority class, canonical URL, retrieval/publication times and fingerprints. Full pages, profiles, provider responses and temporary extraction content are not retained. Current UI claims are built from the latest usable run; history remains immutable. A later run can show new, changed or no-longer-supported claims without rewriting the earlier run.

Public statements remain public Prospect research. They never acquire `customer_direct` origin and cannot support customer Evidence, Methodology, Stakeholder Intelligence, Revenue Brain or Ask RevenueOS in WO-027.
