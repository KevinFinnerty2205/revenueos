# Native CRM security and privacy review

## Controls delivered

- Verified tenant/membership supplies organisation context; record/custom/history repositories add explicit organisation predicates.
- New tenant tables use organisation keys, composite membership/definition FKs and PostgreSQL forced RLS; RLS tests exercise cross-organisation denial.
- CRM mode and schema administration require admin plus Core commercial access;
  external mode also requires CRM connector entitlement. Plan mutation is not exposed
  to organisation admins. Owner assignment validates active same-organisation
  membership; members can assign only themselves.
- Exact domain/email duplicates are enforced by service checks and unique indexes. Safe responses expose only entity type/ID, never the conflicting value.
- Custom fields are bounded, strictly typed, non-executable and rendered as text. URLs accept HTTP(S) only; arbitrary HTML/JSON, formulas and scripts are unsupported.
- Optimistic concurrency prevents silent overwrites. External authority is enforced server-side even if a client ignores disabled controls.
- Archive/restore requires an entitled administrator and archived records reject mutation. Hard privacy deletion stays in the existing maintenance lifecycle and removes polymorphic CRM values/history before the canonical row.
- Operational logs receive route/status/safe codes and request IDs, not business emails, custom values, history diffs, prompts/transcripts or provider payloads.

## Threat review

| Risk                                    | Mitigation                                                                                             |
| --------------------------------------- | ------------------------------------------------------------------------------------------------------ |
| Cross-tenant record or field attachment | Tenant-scoped lookup before mutation, composite FKs where possible, forced RLS                         |
| Ownership spoofing/inactive assignee    | Same-org active-membership check plus role policy                                                      |
| Duplicate race                          | Database unique index; safe conflict response                                                          |
| External/local sync fight               | Explicit mode, active mapping authority, read-only UI and API rejection                                |
| XSS/unsafe URL                          | Text-only controls/React escaping and server HTTP(S) validation                                        |
| Schema/workflow abuse                   | Six types, 25 active/type, 50 options, no execution/relations/required fields                          |
| Sensitive history leakage               | Tenant-only API, bounded safe fields, no operational log payloads; deletion lifecycle includes history |
| Archive mistaken for erasure            | UI/API language separates archive/restore from privacy deletion                                        |
| Bulk exfiltration/import abuse          | Operational CSV deliberately absent; organisation export retains existing privileged process           |

No real external provider call occurs in standard tests. HubSpot authority tests seed local mapping rows only.
