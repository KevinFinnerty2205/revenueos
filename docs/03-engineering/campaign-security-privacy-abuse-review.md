# Campaign security, privacy and abuse review

- **Review result:** acceptable for bounded private-beta simulation with production
  fail-closed

## Controls

- six new tenant tables have explicit organisation predicates, composite tenant keys,
  forced PostgreSQL RLS and cross-tenant tests;
- request contracts accept at most 50 unique canonical Contact IDs and four steps;
- no arbitrary email, CSV, purchased-list, self-expanding audience or provider
  response enters the Campaign API;
- launched audience/sequence/policy authority is immutable and auditable;
- organisation suppression is non-overridable and checked again before execution;
- verified address is treated as contact-data trust, not legal permission;
- sender membership, mailbox ownership, policy, entitlement and feature state fail
  closed;
- cooldown, user/org daily quotas, campaign caps, preparation caps and collision rules
  prevent uncontrolled volume;
- sensitive/private research and unsupported claims remain excluded by WO-029;
- unknown provider outcome never auto-retries; and
- metadata-only logs/metrics exclude names, addresses, subject/body, source excerpts,
  credentials, OAuth material and raw provider payloads.

## Explicit non-capabilities

No live Gmail/Graph send, inbox read, automatic reply detection, tracking pixel,
open/click tracking, sender/domain rotation, warm-up, spam-evasion, A/B testing,
send-time ML, LinkedIn automation, cold calling, event workflow, autonomous SDR or
customer-intelligence mutation was added. Automated tests use synthetic Contacts and
Mock Email only; no real email is sent and no paid service is activated.

## Residual risk

An organisation remains responsible for lawful purpose, consent and jurisdictional
requirements; product controls are not legal advice. Production sending additionally
requires approved mailbox OAuth/send/reconciliation, bounce/complaint/opt-out
operations, incident response and deployment review. Until then production campaign
launch and worker execution are unavailable.
