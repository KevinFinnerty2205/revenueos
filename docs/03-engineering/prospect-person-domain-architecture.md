# Prospect Person domain architecture

## Decision

`ProspectPerson` is a tenant-owned research entity beneath `ProspectResearchTarget`; it is not a subtype of canonical `Contact`. A composite `(organisation_id, target_id)` relationship enforces company scope. Provider identity is unique only within organisation, target and provider.

WO-027 reuses the immutable Prospect pipeline by adding nullable `person_id` to `prospect_research_runs`. Company runs always query `person_id IS NULL`; person runs carry the person and target. Existing source, observation, source-link, lifecycle, lease and retry semantics remain authoritative.

New tenant tables are `prospect_people`, `prospect_buying_role_hypotheses`, `prospect_buying_role_sources`, `prospect_contact_points` and `contact_field_sources`. Migration `0036_prospect_people` enables and forces PostgreSQL RLS on every new table. Composite foreign keys prevent cross-target or cross-tenant attachment.

The current API surface is company-scoped discovery/listing, person read/research/refresh/delete, buying-role review, explicit person promotion and the Contact research link. Route handlers remain thin; `ProspectPeopleService` owns policy and `ProspectRepository` owns tenant predicates.

No new queue was introduced. The existing PostgreSQL-compatible Prospect worker claims company and person runs. Person refresh updates only the Prospect Person employment state and creates a new immutable research version; it never edits the promoted Contact or downstream truth domains.
