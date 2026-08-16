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

## Separate execution lifecycle

WO-022 does not add execution states to the Action review state machine. A current
`approved` Action may have zero or one idempotent execution for a given approved
version, connection and capability. Its separate lifecycle is:

```text
queued ──claim──> executing ──> simulated_success
  │                   ├───────> failed_retryable ──bounded retry──> executing
  │                   ├───────> failed_permanent
  │                   └───────> unknown_external_state
  └──connection revoke────────> cancelled
```

Unknown state is terminal until a future reconciliation workflow exists. Action
approval remains intact even when its simulation fails or is cancelled.
