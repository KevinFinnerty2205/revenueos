# Contact provenance architecture

`contact_field_sources` records provenance for canonical Contact fields created or matched through Prospect Person promotion. Each row contains organisation and Contact scope, field key, value fingerprint, source type, nullable Prospect Person link, provider key, trust, observed/verified times and active state.

The design deliberately avoids one aggregate “Contact verified” flag. Email, phone, job title and LinkedIn URL can have different trust. WO-027 promotes only supported email, current public job title and an actual permitted LinkedIn URL; a generic professional-profile URL remains on the Prospect Person and phone remains absent under the v1 policy. Provider-supplied email remains `provider_supplied`, while `verified_at` is populated only for truly verified values.

Attach-research never overwrites canonical fields. Create-separate requires explicit duplicate review. Later Prospect refresh does not propagate changes. If provider contact data expires, retention compares the stored fingerprint with the current Contact value, clears only an unchanged matching field, deactivates its provenance and preserves the Contact. Deleting Prospect Person research nulls the source link where required but does not delete the Contact.

The provenance table is tenant-scoped with forced RLS. It contains hashes and metadata, not raw provider payloads or hidden provider person identifiers.
