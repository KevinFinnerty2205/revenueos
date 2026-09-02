# Native CRM retention, export and deletion

Canonical records and CRM metadata follow organisation retention; archive does not shorten or reset it. Archive hides records from normal lists while preserving relationships, custom values, activity sources and change history. Restore reverses that state. There is no ordinary hard-delete button.

Organisation export version 29 serialises the core fields, archive timestamps, CRM
setting, field definitions, typed values, record changes, Pipeline definitions/current
assignment, immutable stage events, closure metadata and content-free import/merge/
provisioning history. Values remain structured and
source-labelled. It does not include credentials, HubSpot tokens, transcripts,
Evidence content or raw provider/research payloads merely because CRM is enabled. See
the [Pipeline lifecycle guide](native-pipeline-retention-export-deletion.md).

Preview retention deletes expired unconfirmed CRM import batch/row metadata; no raw CSV
exists to clean up. Merge tombstones/history remain with CRM history until organisation
erasure. Organisation deletion removes import/merge/provisioning metadata,
values/history/settings/definitions and canonical records through the reviewed graph.
Canonical record privacy deletion/cascade rules remain the owner of related data. If an
authorised erasure requires field-history redaction, use the existing privacy
maintenance process rather than archive. Operational logs contain no CRM values to scrub.

Entitlement loss is not deletion: Core records remain usable and custom fields remain
visible read-only. CSV is an inbound supervised onboarding format, not a new CSV export;
the versioned organisation export remains the portability contract.
