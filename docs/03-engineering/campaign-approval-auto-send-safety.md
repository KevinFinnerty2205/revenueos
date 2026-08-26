# Campaign approval and auto-send safety

`review_each_send` remains the default and strongest mode. Preparing a Campaign step
creates the same immutable Outreach/Action records as WO-029. The sender must approve
the exact current version, inspect the exact Execution Preview and confirm execution.

Bounded auto-send is a two-level policy:

- `outreach_policies.campaign_auto_send_allowed` is administrator-controlled and
  policy-versioned; and
- the campaign owner explicitly selects auto-send and confirms the launch warning.

Launch records approver, time, policy version/fingerprint and immutable launch
fingerprint. When due, the scheduler stores the exact source-backed message before
calling the existing approval/preview/confirm services. Its approval audit records
`approval_basis=campaign_launch` and the exact campaign step-instance ID. Approval
still does not mean execution.

Every due send fails closed on entitlement/feature state, membership/sender,
recipient snapshots, Contact business-email trust, suppression, cooldown/quota,
active Opportunity, campaign collision, current policy fingerprint, current source
trust/freshness and a sender-bound mailbox. A material policy change or Engage
disable cancels queued retryable work and places the Campaign/enrolments in needs
attention. Production is unavailable until a separately approved mailbox slice is
implemented.
