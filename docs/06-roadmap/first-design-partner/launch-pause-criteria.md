# Design-partner launch pause criteria

These criteria apply before and during supervised real-data testing. Any immediate-pause event stops onboarding/import and affected product use without waiting for a roadmap, sales or provider decision.

## Immediate pause

- suspected or confirmed cross-tenant read, write, search, export, object, grant, worker or cache access;
- customer data loss, unexplained corruption, wrong-tenant attachment or canonical record mismatch;
- backup failure, missed approved RPO, inability to restore, checksum mismatch or unproved private-object recovery;
- authentication/session/member revocation outside the approved maximum or a disabled user retaining access;
- incorrect Evidence source/attribution, customer/seller origin collapse or correction not propagating as promised;
- unsafe Create output, review/download mismatch, missing required/legal content, corrupt file or unauthorised download;
- contactability/suppression regression, imported email treated as permission or prohibited outreach eligibility;
- any external mutation, provider transmission or message outside the exact approved feature/provider/human approval;
- secret, bearer token, signed URL, transcript, prompt, CSV row, document/email content or provider payload in logs/tickets;
- object storage public exposure, encryption failure or runtime database role with superuser/`BYPASSRLS`;
- deletion/export/offboarding cannot be completed or verified as described; or
- legal/privacy/AI/partner approval expires, is withdrawn or no longer matches the target configuration.

## Response

1. Stop the import or affected user workflow; disable the narrow feature and worker claims. If tenant scope is uncertain, stop affected API/worker traffic.
2. Preserve content-safe request IDs, timestamps, release/config identifiers and logs. Do not copy additional customer content.
3. Notify the incident commander, security/privacy owner, engineering owner and authorised partner contact through the approved route.
4. Revoke/rotate affected sessions or credentials. Never switch to mock intelligence over real data or blindly retry an unknown external state.
5. Follow the existing private-beta incident runbook and obtain legal/privacy guidance for communication/notification duties.
6. Fix forward with a regression test where code is involved; repeat the complete affected target proof, not only the failing step.
7. Resume only after the accountable owners record cause, scope, recovery, verification and explicit re-authorisation.

## Normal product issues

Ordinary copy/layout friction, a discoverability problem or a non-blocking workflow inconvenience can be logged and prioritised normally only when it has no data-integrity, security, privacy, permission, provider, recovery or trust effect. Repeated UX failure that prevents the flagship workflow is escalated to a pause even if no data was exposed.

Supervision is not a mitigation for a known immediate-pause condition. If uncertain, pause and classify with the security/operations owner.
