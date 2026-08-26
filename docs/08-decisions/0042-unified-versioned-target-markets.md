# ADR 0042: Unified, versioned Target Markets

## Context

ICP describes who fits; territory describes where and which segment a seller covers.
Separate top-level objects would make first use harder and could produce conflicting
definitions. Discovery also needs historical criteria to explain old results.

## Decision

Use **Target Market** as the single user-facing aggregate containing bounded ICP and
territory criteria. Keep a mutable aggregate for name/status/current revision, append
immutable definition revisions and attach each immutable discovery run to one exact
revision. Reuse Prospect Research Target for company identity and keep canonical
Company/Opportunity relationship state contextual and read-only.

Prioritisation is deterministic and categorical with persisted reasons. Unknown is a
first-class state. No score, purchase-intent claim or automatic downstream mutation
is introduced.

## Alternatives

- **Separate ICP and Territory objects:** rejected for this slice because it doubles
  administration and permits ambiguous combinations before users need that power.
- **Mutable filters on each run:** rejected because historical results would become
  unexplainable after editing.
- **Provider score as priority:** rejected because it is opaque, provider-coupled and
  risks being mistaken for intent.

## Consequences

The first-time workflow stays guided and historical runs remain auditable. A future
ownership-routing territory model can be added separately if real assignment needs
emerge. Schema and export cost are higher because revisions and results persist until
approved organisation deletion.
