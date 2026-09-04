# First-partner support, privacy and incident contacts

- **Status:** **PARTLY RESOLVED — ROUTES VERIFIED; HUMAN OWNERS AND OPERATING PROCESS REQUIRED**
- **Minimum:** one monitored mailbox, three clear functions, two accountable humans

The owner approved `support@oryntela.com.au` as the shared customer-support and
private-beta privacy/security address. Synthetic inbound and matching outbound reply
tests passed, and SPF, DKIM and DMARC passed at the external receiving system. The
primary accountable human, backup human, operating hours and emergency escalation
route remain unresolved. No value may be inferred from a Git identity, personal
email, domain or placeholder.

## Simplest safe arrangement

One secured and actively monitored mailbox serves all three private-beta functions:

- `support@oryntela.com.au` — product access, data-quality and workflow help;
- `support@oryntela.com.au` — access/export/correction/deletion and privacy questions;
  and
- `support@oryntela.com.au` — suspected unauthorised access, disclosure, credential
  or service-security incidents.

This address is a zero-cost alias of `kevin@oryntela.com.au`, the single paid Zoho
mailbox. `hello@oryntela.com.au` is the separate general-enquiries alias. No
`privacy@` or `security@` address exists, and neither should be published.

## Owner inputs required

| Field                   | Requirement                                                                                                         | Current status                                                              |
| ----------------------- | ------------------------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------- |
| Support email           | Public, monitored address                                                                                           | `support@oryntela.com.au` — **APPROVED; ROUTING VERIFIED**                  |
| Privacy email           | May be the same mailbox/alias; public and monitored                                                                 | `support@oryntela.com.au` — **APPROVED FOR PRIVATE BETA; ROUTING VERIFIED** |
| Security/incident email | May be the same mailbox/alias; monitored with urgent escalation                                                     | `support@oryntela.com.au` — **APPROVED FOR PRIVATE BETA; ROUTING VERIFIED** |
| Primary human           | Name/role authorised to triage, communicate and invoke launch pause                                                 | **OWNER INPUT REQUIRED**                                                    |
| Backup human            | Name/role who can act when the primary is unavailable                                                               | **OWNER INPUT REQUIRED**                                                    |
| Operating hours         | Timezone and days/hours the beta is supervised                                                                      | **OWNER INPUT REQUIRED**                                                    |
| Emergency route         | How the mailbox alerts the primary/backup for urgent security events; do not publish personal details unnecessarily | **OWNER INPUT REQUIRED**                                                    |

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

Zoho Mail is recorded in the
[subprocessor register](first-partner-subprocessor-register.md). Its operational
selection does not itself approve the legal/privacy schedule or authorise real
partner data.

## Implementation after approval

The mailbox and public address are active, and the synthetic
support/privacy/security routing exercise passed. Codex can place the approved
support address in production configuration and owner-approved partner/legal
documents after the remaining gate approvals. Human ownership, alerting, hours and
escalation remain owner decisions.
