# RevenueOS Daily security and privacy review

- **Status:** Reviewed for WO-025
- **Data model:** Computed read only; no migration or retained Daily snapshot

## Authorisation

Daily derives organisation/user only from verified authentication, rechecks active
membership and sets the trusted tenant transaction context before reads. Every query
has an explicit organisation predicate. Personal scope is additionally enforced:

- Interactions must be created by the current user;
- Opportunities and pipeline records must be owned by the current user; and
- Actions must be created by the current user and belong to an Opportunity they own.

Admin receives the same personal plan; team visibility is not inferred from role.
Tests cover active admin/member, disabled membership, another organisation and
another user inside the same organisation. Existing forced PostgreSQL RLS and tenant
composite keys remain defence in depth; no privileged Daily repository exists.

## Content minimisation

Daily does not select or return transcripts, transcript segments, email/document
bodies, Evidence values, prompts, generated reasoning arrays, confidence, provider
payloads, recipient fields or execution payloads. It validates persisted methodology,
Revenue Brain and Next Best Action contracts and maps them to controlled, product-safe
summary text. Malformed optional derived content is ignored.

Customer/account/opportunity/action names are response content for the authorised
user but are never included in Daily telemetry. Internal source Evidence IDs and
provenance arrays are absent. The small IDs returned exist only for stable source-page
links.

## Logging and failure

`daily_opened` is metadata-only: organisation/user IDs, local date, timezone,
controlled priority type, bounded counts and partial flag. `daily_source_unavailable`
adds only the source key. No name, title, reason text, customer content, query string,
provider detail or stack trace is logged by Daily.

Optional SQL source failure is isolated with a savepoint and rendered unavailable;
auth and membership failures remain terminal. No destructive action exists on Home.
Action CTAs lead to the existing review/confirmation boundaries, so Daily cannot
approve, execute, send or mutate customer state by itself.

## Retention and export

Daily creates no customer-data row, cache or browser-stored snapshot. Existing source
retention/export/deletion behaviour is unchanged. No employee activity monitoring,
presence polling, screen-time tracking or surveillance was added.
