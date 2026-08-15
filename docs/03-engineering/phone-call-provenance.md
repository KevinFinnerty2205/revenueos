# Phone-call provenance

Phone-call metadata, recording evidence and the seller's recollection are separate
sources beneath one Interaction.

| Source                               | Origin/support                                                | Review and downstream behaviour                                      |
| ------------------------------------ | ------------------------------------------------------------- | -------------------------------------------------------------------- |
| Direction, outcome and elapsed time  | `system_metadata`                                             | Timeline metadata; never customer intent                             |
| Typed Debrief or Voice Journal       | `salesperson_reported` / `reported`                           | Candidate review required; displayed **Reported by you**             |
| Imported recording source Evidence  | `imported_external` / `direct`, plus controlled source label  | Produces an immutable transcript; source is retained                 |
| Foreground live recording Evidence  | `customer_direct` / `direct` under the existing WO-015 policy | Not offered as normal phone-call capture in the browser              |
| Transcript segments                  | Derived from one immutable recording transcript version       | Speaker labels are not automatically mapped to Contact identities    |

## Reconciliation

The debrief context receives bounded direct-recording coverage metadata. At finish,
the deterministic reconciliation reads the tenant-scoped final transcript only
inside the trusted service and labels each reported candidate:

- `corroborated` when the recording contains compatible material;
- `conflicting` for controlled incompatible states such as approved/not approved,
  agreed/not agreed or confirmed/unclear;
- `unresolved` when both sources exist without safe deterministic alignment; or
- `not_assessed` when no final recording transcript is available.

The raw transcript is not sent as ordinary question-selection context, copied into
audit metadata or returned as a reconciliation explanation. Conflict remains
visible in review, Opportunity Workspace and the immutable Interaction/Revenue Brain
snapshot. A user edit does not turn reported evidence into customer-direct evidence,
and recency never silently wins.

Recording transcript Evidence and accepted debrief Evidence remain independently
exportable/deletable through their existing lineage. Deleting a recording removes
objects first and makes dependent current use ineligible; immutable history follows
the approved content-minimised deletion policy.
