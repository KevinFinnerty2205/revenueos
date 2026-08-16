# Integrations and execution foundation

**Status:** Implemented by WO-022 for development and private-beta simulation only.

WO-022 lets an organisation administrator enable deterministic mock email,
calendar, CRM and task connections. An active organisation member may then take
an already approved Action through a separate server-generated preview and final
confirmation. The result is an auditable simulation; RevenueOS does not contact
or mutate an external provider.

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

| Connector | Capability | Risk class | Simulated result |
| --- | --- | --- | --- |
| Mock Email | Send email | External customer-facing | Deterministic mock email ID |
| Mock Calendar | Create event | External customer-facing | Deterministic mock event ID |
| Mock CRM | Update one Opportunity or Contact field | Data mutation | Tenant-scoped mock external value |
| Mock Tasks | Create task | Internal low-risk | Deterministic mock task ID |

## Known limitations

There are no real Gmail, Outlook, Microsoft 365, Google Workspace, Salesforce,
HubSpot, Dynamics, calendar, Slack, Teams or task-system connections. There is no
real OAuth exchange, webhook ingestion, browser automation, autonomous execution
or direct tool use by AI. A future live adapter requires a separate work order,
provider/privacy review and production release gate.

See the [preview and confirmation guide](../03-engineering/execution-preview-confirmation.md),
[simulation mode](../03-engineering/simulation-mode.md) and
[Action execution boundary](../05-integrations/action-execution-boundary.md).
