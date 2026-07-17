# User journeys

**Status legend:** **Current** exists now; **Pilot** is required for the first five design partners; **Beta** is required for private beta; **Later** is deliberately deferred; **Future** is a concept only.

Time-saved estimates are hypotheses to measure during the pilot. They are not guaranteed customer outcomes.

## 1. Organisation setup — Beta

- **Trigger:** An authorised administrator starts a RevenueOS organisation.
- **Steps:** Verify identity; create or link the organisation; confirm region and policy defaults; invite initial members; assign roles; review readiness.
- **System behaviour:** Resolves one trusted tenant context, records configuration changes and keeps unavailable capabilities visibly disabled.
- **User control points:** Administrator chooses membership, role, retention and whether connectors may be enabled.
- **Failure states:** Identity or membership mismatch, duplicate organisation, invitation failure, unsupported region or incomplete policy.
- **Trust and privacy:** No client-supplied organisation identifier is trusted; defaults minimise retention and privileges.
- **Expected time saved:** 30–60 minutes per initial setup after the process is repeatable.

## 2. User onboarding — Beta

- **Trigger:** An invited member signs in for the first time.
- **Steps:** Accept invitation; confirm role and organisation; review capture/consent responsibilities; select notification preferences; complete a guided first workflow.
- **System behaviour:** Shows only authorised organisation data and records policy acknowledgement without presenting it as legal advice.
- **User control points:** User chooses preferences and may skip non-essential personalisation.
- **Failure states:** Expired invitation, removed membership, wrong organisation, unavailable connector or incomplete acknowledgement.
- **Trust and privacy:** Explain what is collected, which actions require approval and how to delete or exclude content.
- **Expected time saved:** 15–30 minutes compared with administrator-led onboarding.

## 3. Connect calendar and email — Pilot one ecosystem; Beta both ecosystems

- **Trigger:** An administrator or authorised user enables Google Workspace or Microsoft 365.
- **Steps:** Review requested scopes; complete OAuth; select calendars/mailbox; verify connection; choose allowed workflows; run a metadata-only test.
- **System behaviour:** Stores encrypted tokens outside browser reach, reports granted scopes and separates calendar reads from mail draft/send permissions.
- **User control points:** Connection owner can decline scopes, disable ingestion, require per-action approval and revoke access.
- **Failure states:** Consent denial, tenant admin approval required, expired token, webhook loss, rate limit or revoked account.
- **Trust and privacy:** Least privilege, no historic mailbox bulk ingestion by default and no send without recorded approval.
- **Expected time saved:** 10–20 minutes per user each week once preparation and approved follow-up are active.

## 4. Connect CRM — Pilot one CRM; Beta Salesforce and HubSpot

- **Trigger:** An authorised administrator enables the organisation's CRM.
- **Steps:** Review scopes; authenticate; select objects/fields; test reads; configure matching; configure fields eligible for proposals; enable approved writes separately.
- **System behaviour:** Imports only required metadata, stores external identities, shows source-of-truth rules and keeps read, propose and write capabilities distinct.
- **User control points:** Administrator controls mappings and write eligibility; user approves each beta write.
- **Failure states:** Missing scopes, mapping conflict, duplicate record, validation rejection, rate limit, expired credentials or provider outage.
- **Trust and privacy:** CRM stays authoritative; no silent writes; every attempt records source, approver, payload digest and outcome.
- **Expected time saved:** 5–15 minutes of data entry per completed meeting.

## 5. Prepare for a meeting — Pilot

- **Trigger:** A selected meeting is approaching or the user requests a brief.
- **Steps:** Open the brief; verify participants/account; review recent relationship events, commitments and risks; inspect citations; add personal questions.
- **System behaviour:** Uses authorised, current sources; marks stale or conflicting facts; never claims access to an unavailable system.
- **User control points:** User can correct matching, hide an item, mark memory stale or dismiss the brief.
- **Failure states:** Unmatched attendee, insufficient evidence, stale connection, private event, deleted source or generation failure.
- **Trust and privacy:** Brief is scoped to authorised records; inference and confirmed fact are visually distinct.
- **Expected time saved:** 10–20 minutes per meeting.

## 6. Capture a remote meeting — Pilot manual; Beta selected connected platforms

- **Trigger:** A user deliberately uploads a recording/transcript or selects an eligible completed meeting.
- **Steps:** Confirm consent/authority; choose source; upload or import; monitor ingestion; resolve participants; enter review.
- **System behaviour:** Quarantines files, validates type/size/duration, records consent evidence, runs bounded durable jobs and shows progress.
- **User control points:** User initiates capture, may cancel before processing and may delete the source.
- **Failure states:** Unsupported or unsafe file, missing recording, provider access loss, transcription failure, duplicate ingestion or consent not confirmed.
- **Trust and privacy:** No implicit capture; private storage; configurable raw-audio retention with a 30-day default after successful transcription.
- **Expected time saved:** 20–40 minutes of notes and administration per meeting.

## 7. Capture a phone call — Later

- **Trigger:** A user explicitly selects a supported call recording or arms a provider-specific capture workflow.
- **Steps:** Confirm applicable consent; identify call; import source; verify participants; process and review.
- **System behaviour:** Displays an active capture state and provider provenance; applies regional and organisation policy.
- **User control points:** Explicit start/selection, cancel, exclusion and deletion.
- **Failure states:** Jurisdiction restriction, missing consent evidence, provider failure, poor audio or unknown caller.
- **Trust and privacy:** No background call monitoring; phone-provider support requires legal and policy review.
- **Expected time saved:** Hypothesis of 15–30 minutes per substantive call.

## 8. Capture an in-person meeting — Future concept

- **Trigger:** A participant deliberately arms a visible capture experience.
- **Steps:** Confirm organisation policy and participant consent; show capture indicator; start; allow pause/stop; upload; review.
- **System behaviour:** Refuses silent background activation and records who initiated, when consent was confirmed and capture state changes.
- **User control points:** Explicit arm/start/pause/stop, participant exclusion and immediate deletion.
- **Failure states:** Consent withheld, device permission denied, unclear jurisdiction, interrupted capture or unsafe environment.
- **Trust and privacy:** Must respect applicable law and social expectations; a native mobile companion is not beta scope.
- **Expected time saved:** Unvalidated until a lawful, trusted design is tested.

## 9. Review a meeting — Pilot

- **Trigger:** Ingestion and available analysis finish, or a failure requires attention.
- **Steps:** Verify meeting/account/participants; inspect transcript; review summary, next steps, memory candidates, follow-up and CRM proposals; correct, approve, reject or defer each item.
- **System behaviour:** Groups outputs by confidence and consequence, links claims to transcript segments and preserves edits.
- **User control points:** Nothing external executes from opening the review; user chooses every accepted artefact and action.
- **Failure states:** Partial transcript, speaker mismatch, unsupported claim, conflicting CRM data, analysis timeout or source deletion.
- **Trust and privacy:** Raw source access follows permissions; correction provenance and AI version remain auditable.
- **Expected time saved:** Review completed in 5–10 minutes rather than 20–40 minutes of manual work.

## 10. Approve a follow-up — Pilot

- **Trigger:** A meeting has a source-backed follow-up draft.
- **Steps:** Inspect recipients and citations; edit content; preview destination; approve draft creation or, where supported, approved send; inspect receipt.
- **System behaviour:** Revalidates recipient, connection and approval immediately before execution; stores status without logging body content.
- **User control points:** Edit, reject, save as private draft, approve once or cancel before execution.
- **Failure states:** Wrong or missing recipient, unsafe content, expired approval, token failure, provider rejection or uncertain send outcome.
- **Trust and privacy:** No silent communication; approval is bound to a specific content version and recipients.
- **Expected time saved:** 5–10 minutes per follow-up.

## 11. Approve CRM updates — Pilot

- **Trigger:** Reviewed meeting evidence supports one or more eligible CRM changes.
- **Steps:** View field-level diff and source; edit or remove fields; approve; execute idempotently; view confirmation or recovery action.
- **System behaviour:** Rechecks external version and policy, prevents stale overwrite, records each operation and reconciles ambiguous outcomes.
- **User control points:** Approve selected fields only, reject, edit, defer or retry after revalidation.
- **Failure states:** Record conflict, validation error, insufficient scope, rate limit, deleted record or unknown execution result.
- **Trust and privacy:** CRM remains authoritative; no bulk or silent writes during beta.
- **Expected time saved:** 5–15 minutes per meeting while improving traceability.

## 12. Manage tasks — Current foundation; Pilot meeting-derived tasks

- **Trigger:** A user creates a task or reviews a suggested next step.
- **Steps:** Create or accept; link relationship context; assign owner; set due time/priority; update status; open source evidence where available.
- **System behaviour:** Current CRUD stays tenant-scoped; later suggestions remain proposals until accepted.
- **User control points:** User edits, assigns, completes or cancels; AI cannot silently create accountable work.
- **Failure states:** Invalid relationship, removed assignee, inaccessible source, stale suggestion or save failure.
- **Trust and privacy:** Only same-tenant relationships may be linked; sensitive excerpts are not copied into notifications.
- **Expected time saved:** 2–5 minutes per meeting plus fewer missed commitments.

## 13. View a relationship timeline — Pilot

- **Trigger:** A user opens a company, contact or opportunity context.
- **Steps:** Review chronological events; filter by type/source; open evidence; inspect changes; correct or exclude derived memory.
- **System behaviour:** Combines authorised events without claiming to replace external history; labels source and sync state.
- **User control points:** Filter, correct, hide from briefing, request deletion and report mismatch.
- **Failure states:** Missing source, revoked connection, duplicated event, ordering conflict or partial deletion.
- **Trust and privacy:** Permissions apply to each source; restricted content is not revealed through summaries.
- **Expected time saved:** 5–15 minutes when reconstructing account history.

## 14. Ask the assistant about an account — Beta

- **Trigger:** A user asks a question from an authorised company, contact or opportunity context.
- **Steps:** Enter question; inspect answer and citations; open sources; refine; correct or report unsupported content.
- **System behaviour:** Retrieves only tenant-authorised evidence, says when evidence is insufficient and has no implicit write or communication tools.
- **User control points:** Choose context, inspect sources, reject answer and convert a suggestion only through a separate approval workflow.
- **Failure states:** No evidence, conflicting sources, retrieval failure, unsafe request or model timeout.
- **Trust and privacy:** Answers cannot broaden access; prompt and output handling follows confidential-data controls.
- **Expected time saved:** 5–10 minutes per account question.

## 15. Manager pipeline review — Beta

- **Trigger:** A scheduled review or material relationship exception.
- **Steps:** Open exceptions; filter by team/stage; inspect evidence and recency; discuss with owner; assign an agreed action.
- **System behaviour:** Surfaces stalled commitments, changed risk and missing follow-through without presenting opaque performance scores.
- **User control points:** Manager and representative can correct context, dismiss a signal and record a human decision.
- **Failure states:** Stale CRM snapshot, insufficient evidence, changed ownership or overly broad permissions.
- **Trust and privacy:** Coaching access is role- and policy-bound; raw transcript access is not assumed.
- **Expected time saved:** 15–30 minutes per pipeline review while increasing coaching depth.

## 16. Correct AI memory — Pilot

- **Trigger:** A user sees incorrect, stale or misleading relationship memory.
- **Steps:** Open provenance; edit, mark stale, supersede or delete; provide an optional reason; confirm affected briefs/artifacts.
- **System behaviour:** Preserves an audit event, stops serving invalid memory and queues bounded regeneration where necessary.
- **User control points:** Correction is explicit and reversible where retention policy permits; deletion is distinct from supersession.
- **Failure states:** Source already deleted, concurrent edit, insufficient permission or derived artefact not yet refreshed.
- **Trust and privacy:** Corrections do not train provider models by default and do not expose the editor's note beyond authorised users.
- **Expected time saved:** Prevents repeated correction; target under two minutes per item.

## 17. Delete or exclude sensitive information — Pilot

- **Trigger:** A user or administrator identifies data that should not be processed, displayed or retained.
- **Steps:** Select source/item; choose exclusion, redaction or deletion; review impact; confirm; monitor completion; receive outcome.
- **System behaviour:** Blocks future retrieval immediately, cascades deletion according to policy, records metadata-only audit evidence and reports lawful retention exceptions.
- **User control points:** Scope is explicit; authorised users may cancel before irreversible execution where safe.
- **Failure states:** Provider deletion unavailable, legal hold, partial derived-data failure, backup expiry pending or insufficient permission.
- **Trust and privacy:** Deletion claims distinguish active systems, connected systems and expiring backups; raw content is absent from audit logs.
- **Expected time saved:** A single controlled workflow instead of manual requests across RevenueOS stores.

## 18. Handle failed ingestion or low-confidence output — Pilot

- **Trigger:** A job fails, completes partially or produces output below a policy threshold.
- **Steps:** Open exception; view safe reason and affected stage; correct source/matching or retry; upload replacement; continue manually or delete.
- **System behaviour:** Never presents partial output as final, retries only safe transient failures, avoids duplicate processing and preserves diagnostic metadata.
- **User control points:** Retry, replace, bypass an optional step, review manually or delete.
- **Failure states:** Permanent unsupported source, repeated provider failure, unresolvable participant match, exhausted retry or deleted input.
- **Trust and privacy:** Diagnostics exclude raw customer content; confidence labels explain limitations without implying mathematical certainty.
- **Expected time saved:** Recovery in under five minutes for common correctable failures.

## Related documents

- [Master product blueprint](master-product-blueprint.md)
- [Core workflows](../02-design/core-workflows.md)
- [Information architecture](../02-design/information-architecture.md)
- [Integration strategy](../05-integrations/integration-strategy.md)
- [Privacy, security and trust model](../03-engineering/privacy-security-and-trust-model.md)
