# Integrations and execution foundation

**Status:** WO-022 simulation foundation plus WO-025C feature-gated HubSpot live CRM.

WO-022 lets an organisation administrator enable deterministic mock email,
calendar, CRM and task connections. An active organisation member may then take
an already approved Action through a separate server-generated preview and final
confirmation. The result is an auditable simulation; RevenueOS does not contact
or mutate an external provider.

WO-025C extends the same boundary with HubSpot as the sole production CRM adapter.
It supports reviewed Opportunity/Contact field updates and interaction activities,
not autonomous sync. HubSpot is off until OAuth and encrypted credential settings
are complete; simulation connectors remain prohibited in production.

WO-029 adds one-to-one `personalized_outreach` Actions to the same Mock Email
simulation path. It binds the sender to the authenticated user's connection and the
recipient to a canonical Contact, shows the exact approved message and revalidates
Engage entitlement, policy, suppression, address/version and membership at preview,
confirmation and worker execution. Gmail/Microsoft production adapters remain
deferred and fail closed.

WO-030 creates per-recipient Campaign Outreach/Action records and integrates a
leased due-step pass into the existing worker. Review mode stops before approval.
Bounded auto-send may call the same approval, preview and confirmation services only
under versioned administrator policy plus explicit immutable Campaign launch. The
Action worker remains the sole adapter executor and unknown provider state halts the
sequence. Mock Email remains the only mail capability and production still fails
closed.

## User promise

- Approval and execution confirmation remain separate decisions.
- The execution screen is read-only. Recipient, content, attendees, target,
  values, owner and due date come from the approved Action version.
- Customer-facing email/calendar work, external data mutation and internal task
  creation retain their declared risk class through preview and execution.
- Every view and result says that it is a simulation and did not perform a real
  external action.
- Retrying a confirmation cannot create a second simulated side effect.

Administrators create, test and revoke connections. Members may see and use an
active authorised connection but cannot manage it. Revocation invalidates open
previews and cancels queued or retryable simulations immediately.

## Supported simulation capabilities

| Connector     | Capability                              | Risk class               | Simulated result                  |
| ------------- | --------------------------------------- | ------------------------ | --------------------------------- |
| Mock Email    | Send email                              | External customer-facing | Deterministic mock email ID       |
| Mock Calendar | Create event                            | External customer-facing | Deterministic mock event ID       |
| Mock CRM      | Update one Opportunity or Contact field | Data mutation            | Tenant-scoped mock external value |
| Mock Tasks    | Create task                             | Internal low-risk        | Deterministic mock task ID        |

## Live HubSpot capabilities

An admin connects, tests, maps and disconnects HubSpot in Settings. A seller
explicitly links an Opportunity/Contact record, approves an Action, reviews current
and proposed CRM values, then confirms the exact write. Typed authority, stage and
currency rules plus execute-time external reads prevent unsafe overwrite. See
[provider selection](../05-integrations/crm-provider-selection.md).

## Known limitations

There are no real Gmail, Outlook, Microsoft 365, Google Workspace, Salesforce,
Dynamics, calendar, Slack, Teams or task-system connections. There is no broad
webhook/inbound sync, browser automation, autonomous execution or direct tool use
by AI. HubSpot is the only live provider and still requires a target-environment gate.

See the [preview and confirmation guide](../03-engineering/execution-preview-confirmation.md),
[simulation mode](../03-engineering/simulation-mode.md) and
[Action execution boundary](../05-integrations/action-execution-boundary.md).

## WO-023 future integration order

The end-to-end roadmap recommends discovering Microsoft 365 and Google Workspace
needs early, implementing only the first ecosystem justified by design-partner use,
and selecting a first CRM/research provider by customer stack, API quality, scopes,
privacy, cost and operational burden. No provider is selected or implemented by
WO-023. Engage and CRM must extend this simulation-first boundary rather than create
a shortcut around preview, confirmation, idempotency and reconciliation.
