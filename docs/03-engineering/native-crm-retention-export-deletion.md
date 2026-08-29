# Native CRM retention, export and deletion

Canonical records and CRM metadata follow organisation retention; archive does not shorten or reset it. Archive hides records from normal lists while preserving relationships, custom values, activity sources and change history. Restore reverses that state. There is no ordinary hard-delete button.

Organisation export version 24 serialises the new core fields, archive timestamps, CRM setting, field definitions, typed field values and record changes. Values remain structured and source-labelled. It does not include credentials, HubSpot tokens, transcripts, Evidence content or raw provider/research payloads merely because CRM is enabled.

Organisation deletion removes values/history/settings/definitions before canonical records and organisation deletion. Canonical record privacy deletion/cascade rules remain the owner of related data. If an authorised erasure requires field-history redaction, use the existing privacy maintenance process rather than archive. Operational logs contain no CRM values to scrub.

Entitlement loss is not deletion: Core records remain usable and custom fields remain visible read-only. Operational CSV export is deferred, but the organisation export prevents data lock-in until its separately reviewed safe CSV boundary exists.
