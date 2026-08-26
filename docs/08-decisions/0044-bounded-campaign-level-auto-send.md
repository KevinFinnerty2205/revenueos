# ADR 0044: Bounded campaign-level auto-send

## Context

Reviewing every message is safest but can make a short, explicitly approved sequence
impractical. Blanket template approval or autonomous recipient/content selection
would bypass WO-029's exact-version and execution controls.

## Decision

Keep `review_each_send` as default. Permit `approved_campaign_auto_send` only when an
administrator enables it in a versioned organisation policy and the campaign owner
selects it and separately confirms the immutable launch. Store every generated
message before execution and revalidate recipient, suppression, policy, source,
quota, Opportunity, collision and mailbox state at send time. Audit approval basis
and campaign step ID. Halt on change or uncertainty.

## Alternatives

- **Review every message only:** safe but rejects a bounded operational need.
- **Approve a reusable template:** rejected because rendered recipient content and
  sources are not known or pinned.
- **Autonomous SDR:** rejected as deceptive, high-abuse and outside product scope.

## Consequences

Auto-send is narrow, inspectable and revocable but operationally more complex. A
policy/entitlement change stops active work, and production remains unavailable until
mailbox delivery is separately approved.
