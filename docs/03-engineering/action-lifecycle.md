# Action lifecycle

## States

`proposed` is the first review state. Editing creates the next immutable content
version and moves the parent to `edited`. Approval records the current approved
version and reviewer metadata. Rejection records a controlled reason. A later
generation can mark a stale semantic predecessor `superseded`. An approved internal
Action can become `completed_manually` only from explicit user confirmation.

Valid review transitions are:

```text
proposed ──edit──> edited ──edit──> edited
    │                 │
    ├─approve─────────┴─approve──> approved ──manual confirmation──> completed_manually
    ├─reject──────────┴─reject───> rejected
    └─new supported replacement─> superseded
```

Terminal Actions cannot be edited or reviewed again. Expected-version checks reject
stale browser writes. Approval revalidates every source and changes a stale proposal
to `superseded` rather than accepting it.

Audit rows contain event type, actor, proposal version, timestamps and safe bounded
metadata only. Titles, descriptions, drafts, evidence statements and source content
stay out of audit/log payloads.
