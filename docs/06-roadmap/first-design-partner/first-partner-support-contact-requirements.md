# First-partner support, privacy and incident contacts

- **Status:** **OWNER INPUT REQUIRED**
- **Minimum:** one monitored mailbox, three clear functions, two accountable humans

The repository contains no approved support address, privacy address,
security/incident address, primary owner, backup owner or operating hours. No value
may be inferred from a Git identity, personal email, domain or placeholder.

## Simplest safe arrangement

One secured and actively monitored mailbox can safely serve all three functions for
the first supervised partner. If an existing approved domain/mail service supports
aliases, publish three role addresses that route to it:

- `support@…` — product access, data-quality and workflow help;
- `privacy@…` — access/export/correction/deletion and privacy questions; and
- `security@…` — suspected unauthorised access, disclosure, credential or service
  security incidents.

The aliases are examples, not approved addresses. If aliases are unavailable, one
owner-supplied email may be published for all three functions, labelled clearly.
RevenueOS does not need three paid mailboxes for this cohort.

## Owner inputs required

| Field | Requirement | Current status |
| --- | --- | --- |
| Support email | Public, monitored address | **OWNER INPUT REQUIRED** |
| Privacy email | May be the same mailbox/alias; public and monitored | **OWNER INPUT REQUIRED** |
| Security/incident email | May be the same mailbox/alias; monitored with urgent escalation | **OWNER INPUT REQUIRED** |
| Primary human | Name/role authorised to triage, communicate and invoke launch pause | **OWNER INPUT REQUIRED** |
| Backup human | Name/role who can act when the primary is unavailable | **OWNER INPUT REQUIRED** |
| Operating hours | Timezone and days/hours the beta is supervised | **OWNER INPUT REQUIRED** |
| Emergency route | How the mailbox alerts the primary/backup for urgent security events; do not publish personal details unnecessarily | **OWNER INPUT REQUIRED** |

Recommended initial hours are agreed Australian business hours in AEST/AEDT for a
scheduled supervised cohort. Use internal operating targets—not contractual SLAs—of
one business day to acknowledge ordinary support/privacy messages and prompt
same-session escalation of a credible security incident. The signed beta agreement
must state the actual route/hours and avoid an unsupported 24/7 or uptime promise.

## Mailbox safeguards

- MFA for primary and backup; no shared password; least privilege and recovery owner;
- alerts/rules tested with synthetic messages before launch and periodically;
- no transcripts, prompts, CSV rows, customer documents, credentials, authorisation
  headers or provider payloads copied into ordinary tickets;
- use request IDs, timestamps and content-safe `support-bundle` metadata;
- verify authority before account/export/deletion requests and use the existing
  supervised workflow;
- record severity, decision, owner, partner communication and resolution in an
  access-restricted content-minimised incident record; and
- route suspected tenant leak, failed revocation, unsafe AI transfer or unrecoverable
  data corruption directly to the launch-pause procedure.

The actual mailbox provider must be added to the
[subprocessor register](first-partner-subprocessor-register.md) if it processes
partner personal data. Selecting an address does not authorise Codex to purchase a
domain, create mail accounts or send external messages.

## Implementation after approval

Codex can place the approved support address in production configuration and approved
partner/legal documents, configure metadata-only alert routing in the target, and run
a synthetic support/privacy/security routing exercise. Human ownership, mailbox
creation and public addresses remain owner decisions.
