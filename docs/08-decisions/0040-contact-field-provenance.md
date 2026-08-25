# ADR 0040: Preserve trust per promoted Contact field

## Context

Business email, phone, job title and profile URL can come from different sources with different verification and expiry. A Contact-level “verified” flag would erase this distinction during Prospect promotion.

## Decision

Add `contact_field_sources` with field key, value fingerprint, Prospect source relationship, provider, trust, observed/verified timestamps and active state. Promotion preserves source trust and never upgrades `provider_supplied` to `verified`. Expiry can remove an unchanged provider-derived field without deleting the Contact.

## Alternatives

- **Embed one provenance JSON object on Contact:** rejected because tenant constraints, unique values and lifecycle updates would be weak.
- **Copy only values:** rejected because users could not distinguish verification or explain deletion.
- **Never copy contact data:** rejected because explicit promotion should create a useful Contact where licensing permits.

## Consequences

Contact email is nullable so “unknown” is representable for promoted people. Existing manual Contact creation still requires email. Future CRM sync must respect field authority and active provenance rather than assuming all Contact values are equivalent.
