# CRM field-authority model

Integrated CRM mode assumes the external CRM remains the system of record. Every
enabled field mapping stores an explicit authority:

| Value | Read | Propose | Execute |
| --- | --- | --- | --- |
| `review_before_sync` | yes | yes | only after fresh preview and explicit confirmation |
| `crm_authoritative` | yes | may display current value | blocked |
| `revenueos_authoritative` | modelled for future policy | not exposed in v1 UI | still requires reviewed Action in WO-025C |

`review_before_sync` is the database, API and UI default. It applies to stage,
status, close date, amount, next step, description, Contact name/email/title and
future methodology fields. RevenueOS never silently marks itself authoritative.

The admin UI intentionally offers only “Review before update” and “CRM is source
of truth”. Changing authority increments the connection metadata version, which
invalidates older preview fingerprints. Members may use a configured active
connection but cannot alter authority.

Owner, provider-controlled values and read-only properties are not sync targets.
`crm_authoritative` is enforced again inside the HubSpot adapter, not only in the
UI. Future low-risk auto-sync policy must be a separate work order and must not
reinterpret field authority as permission to execute unreviewed AI output.

## WO-034 native-mode reuse

Organisation CRM settings now explicitly choose RevenueOS (`native`) or connected
HubSpot (`external`). Native mode defaults normal local fields to
`revenueos_authoritative`; it does not change evidence trust. External mode uses the
same active mapping rows described above. `crm_authoritative` fields appear read-only
in record/edit UX, are omitted from browser PATCH payloads and remain rejected by the
service. A disconnected external choice is setup-required, and switching to native
is blocked while active mappings exist. No autonomous writer was added.
