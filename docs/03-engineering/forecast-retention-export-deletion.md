# Forecast retention, export and deletion

Forecast follows the owning organisation and Opportunity lifecycle. The private-beta
organisation export schema version 27 includes periods, judgment identities and every
revision/snapshot field. It excludes derived live aggregates, because those can be
recomputed from canonical records and versions.

Ordinary users cannot delete or rewrite forecast history. Organisation deletion
cascades tenant rows. Opportunity hard deletion through approved maintenance cascades
its judgment identities and revisions; period identities may remain while other deals
refer to them. Demo reset uses the explicit transaction-local maintenance flag and
deletes revision → judgment → period before synthetic Opportunities.

There is no new object storage, provider payload, cache or secondary datastore.
Forecast uses the existing organisation/export/erasure controls; no independent
retention clock is introduced in WO-038.
