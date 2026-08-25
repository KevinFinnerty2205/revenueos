# Prospect Person retention, export and deletion

Person targets, runs, sources, observations, source links, hypotheses and contact points follow the organisation Prospect retention window. Active runs are excluded from target deletion. Deleting an aged target cascades research-only person data while any promoted Contact survives.

Contact points also carry provider-specific `expires_at` and `export_allowed`. Retention processes expired active points even when general retention is indefinite. For a promoted Contact, an unchanged matching derived field is cleared and its provenance deactivated; the Contact is not deleted. Future live adapters must set shorter contractual expiry where required.

Organisation export schema version 17 includes Prospect People (without provider person IDs), person run links, professional observations and source metadata, hypotheses/source links, promotion state, permitted contact points and Contact field provenance. Raw provider payloads, hidden person IDs, caches, private/sensitive information and `export_allowed = false` values are excluded.

Person deletion removes the Prospect Person and its research history through tenant-scoped cascades. The UI confirms that an already-promoted Contact remains. Organisation deletion explicitly removes new research/provenance tables in foreign-key order before Core entities. All operations use the trusted tenant setting and forced RLS.

Rollback from migration 0036 to 0035 makes Contact email non-null again; operators must review and resolve any null-email promoted Contacts before downgrade.
