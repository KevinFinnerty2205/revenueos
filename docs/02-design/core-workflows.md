# Core workflows

This document defines target workflows through beta. It does not claim these states or services exist today. Current implementation is limited to the foundation described in the [application architecture](../03-engineering/architecture.md).

## State and approval conventions

- `→` is a valid state transition.
- `[USER APPROVAL]` is a consequential boundary that cannot be bypassed during beta.
- Automated retries apply only to classified transient failures and remain bounded.
- Every transition is tenant-scoped, idempotent where repeated delivery is possible and recorded with safe operational metadata.
- Deleting or excluding a source invalidates dependent output; it must not leave searchable orphaned content.

## 1. Meeting ingestion

**State:** `draft → consent_confirmed → uploaded/imported → quarantined → validated → queued → processing → ready_for_review`

1. User deliberately selects a file, pastes text or chooses an eligible connected source.
2. `[USER APPROVAL]` User confirms consent/authority and intended processing.
3. System records source identity, ingestion idempotency key and consent evidence.
4. File sources remain private in quarantine until size, detected type, duration and safety checks pass.
5. A durable job acquires a lease and advances bounded processing stages.
6. Success creates a reviewable meeting source; it does not approve derived facts or actions.

**Exceptions:** `validation_failed`, `duplicate_detected`, `processing_failed`, `cancelled`, `deleted`. Transient errors may go `processing_failed → retry_queued`; permanent errors require replacement, manual transcript or deletion.

## 2. Meeting review

**State:** `ready_for_review → in_review → reviewed → completed`

1. User verifies meeting identity, participants, company and opportunity.
2. User reviews transcript and each generated artefact with citations and confidence.
3. User edits, accepts, rejects or defers summary, next steps, memory candidates, follow-up and CRM proposals independently.
4. `[USER APPROVAL]` User confirms selected internal artefacts.
5. External actions remain separately pending; “reviewed” never implies sent or synced.

**Exceptions:** Partial results remain labelled `partial`; inaccessible/deleted sources block unsupported approvals; concurrent edits require refresh before approval.

## 3. Transcript correction

**State:** `generated/imported → reviewable → corrected → superseded`

1. User selects a speaker, timestamped segment or text range.
2. User corrects text or attribution and optionally records a reason.
3. System creates a new transcript version, retains edit provenance and identifies affected artefacts.
4. A bounded regeneration proposal is created; accepted external actions are not silently changed.
5. `[USER APPROVAL]` User reviews materially changed outputs again.

**Exceptions:** Deleted source, overlapping concurrent correction and failed regeneration remain visible; the last confirmed version stays available where policy permits.

## 4. Contact and company matching

**State:** `unmatched → candidates_found → suggested → confirmed` or `unmatched → manually_created/linked`

1. Deterministic identifiers (external ID, verified email/domain) narrow same-tenant candidates.
2. Fuzzy or model-assisted evidence may rank candidates but cannot merge them.
3. System shows why each candidate matched and identifies conflicts.
4. `[USER APPROVAL]` User confirms the link or creates a new record.

**Exceptions:** `ambiguous`, `conflicting_identity`, `restricted_record`. Low confidence stays unresolved and blocks relationship memory promotion.

## 5. Duplicate handling

**State:** `suspected → under_review → distinct` or `suspected → merge_proposed → merged`

1. System detects same-tenant duplicate source, identity or record using deterministic keys first.
2. User compares provenance, linked records and consequences.
3. `[USER APPROVAL]` User marks distinct or approves a merge where the product supports a reversible merge.
4. System preserves aliases/external identities and redirects eligible links without crossing tenants.

**Exceptions:** CRM-authoritative duplicates may require correction in the CRM; RevenueOS must not fabricate a successful external merge. Destructive auto-merge is not beta scope.

## 6. Relationship memory creation

**State:** `candidate → source_verified → user_confirmed/auto_eligible → active → stale/superseded/deleted`

1. Meeting review or an authoritative source yields a narrowly defined memory candidate.
2. System stores its claim type, subject, source spans, time, confidence and sensitivity class.
3. Policy decides whether explicit confirmation is mandatory; consequential or uncertain items always require review.
4. `[USER APPROVAL]` User accepts, edits or rejects review-required memory.
5. Active memory can inform briefs and answers while retaining provenance.

**Exceptions:** Unsupported, conflicting or excluded candidates are not activated. Source deletion moves dependent memory to deleted or unsupported according to policy.

## 7. Follow-up drafting

**State:** `candidate_context → draft_generated → user_editing → approved_version → draft_created/sent → confirmed`

1. Reviewed meeting facts and commitments form a bounded prompt context.
2. System generates structured recipients, subject, body and supporting sources.
3. User verifies recipients and edits the draft.
4. `[USER APPROVAL]` Approval binds exact content, recipients, destination and expiry.
5. Provider adapter creates a draft or sends only the approved version; system records a receipt.

**Exceptions:** Unsafe/unsupported output, changed recipient, expired approval, provider rejection and ambiguous delivery return to user attention. No retry may duplicate a send.

## 8. Task extraction

**State:** `candidate → reviewed → accepted → open → in_progress → completed/cancelled`

1. System extracts owner, action, due-time evidence and linked relationship.
2. Missing owner or due date is labelled, not invented.
3. `[USER APPROVAL]` User edits and accepts the candidate.
4. Accepted task becomes accountable work with source provenance.

**Exceptions:** Removed assignee, cross-record mismatch or duplicate commitment blocks acceptance. Rejected candidates are retained only as minimal audit metadata.

## 9. CRM update proposal

**State:** `evidence_identified → mapped → diff_ready → awaiting_approval`

1. Reviewed evidence maps to an administrator-eligible CRM object and field.
2. System reads the current external value/version and creates a field-level diff.
3. Policy removes prohibited or unsupported fields.
4. User sees source, current value, proposed value, confidence and destination.

**Exceptions:** No match, ambiguous record, stale snapshot, unsupported field or insufficient scope returns the proposal for correction; none is reported as a write.

## 10. User approval

**State:** `awaiting_approval → approved/rejected/expired/revoked`

1. User opens a specific proposed action.
2. System rechecks current membership, role, policy, destination and content version.
3. `[USER APPROVAL]` User approves selected fields/content or rejects.
4. Approval stores actor, time, action digest, source references, destination and expiry.
5. Material edits or changed destination invalidate the approval.

**Exceptions:** Membership removal, policy change, stale external version and elapsed expiry fail closed.

## 11. Sync confirmation

**State:** `approved → queued → executing → provider_acknowledged → reconciled → confirmed`

1. Worker claims the operation using a tenant-scoped idempotency key.
2. Adapter executes the least-privilege approved change.
3. Provider identifier/version and response classification are stored without raw secrets or unnecessary content.
4. Read-after-write or webhook reconciliation confirms the authoritative value.
5. UI shows confirmed completion and links the approval and source.

**Exceptions:** A request accepted by the provider but not reconciled stays `provider_acknowledged`, not falsely “complete”.

## 12. Failed sync recovery

**State:** `executing → transient_failed → retry_scheduled → executing` or `executing → permanent_failed/unknown_outcome`

1. System classifies rate limits, authentication, validation, conflict and ambiguous network results.
2. Safe transient failures use bounded exponential backoff.
3. Conflicts and validation failures return a new diff to the user.
4. `[USER APPROVAL]` A materially changed retry requires renewed approval.
5. Unknown outcomes reconcile before any retry that could duplicate an external action.

**Exceptions:** Exhausted retries create an exception notification and preserve a manual recovery path.

## 13. Meeting preparation

**State:** `scheduled/manual_request → context_resolved → brief_generated → available → viewed/stale`

1. Resolve authorised participants, company and opportunity.
2. Gather current CRM snapshot, recent relationship events, active memory and open commitments.
3. Detect conflicts, staleness and missing evidence.
4. Generate a concise structured brief with citations and suggested questions.
5. User can correct matching, exclude an item or refresh.

**Exceptions:** Private event, missing match, deleted source or unavailable connector yields a limited brief that states its evidence boundary.

## 14. Account briefing

**State:** `requested → retrieval_complete → composed → delivered → superseded`

1. User requests a briefing from company/opportunity context.
2. Retrieval applies tenant, source and user permissions before ranking.
3. System composes current state, changes, stakeholders, commitments, risks and next actions.
4. Each material claim links to a source; conflict appears as conflict.
5. Brief expires or refreshes when authoritative data changes.

**Exceptions:** Insufficient evidence produces a useful “known/unknown” result rather than speculation.

## 15. Stale relationship detection

**State:** `eligible → signal_detected → evidence_checked → surfaced → dismissed/actioned/snoozed`

1. Deterministic policy evaluates elapsed time, open commitments and expected next interaction.
2. System verifies source freshness and avoids treating missing integration data as inactivity.
3. An exception explains why attention may be needed.
4. User dismisses, snoozes or creates/updates a task.

**Approval:** Any generated external action follows its normal separate approval workflow. Staleness detection itself cannot send or write.

## 16. Manager coaching and pipeline review

**State:** `review_window → exceptions_compiled → evidence_reviewed → human_decision → follow_up`

1. Policy-authorised manager sees team exceptions and their evidence boundary.
2. Manager and representative inspect relationship changes, commitments and uncertainty.
3. They record a coaching note or agreed action without altering source evidence.
4. `[USER APPROVAL]` The accountable owner accepts any task assigned to them where organisation policy requires it.

**Exceptions:** Restricted transcript, stale CRM data or disputed AI inference stays labelled and cannot become an undisclosed performance score.

## 17. Memory correction and deletion

**State:** `active → correction_requested → corrected/superseded` or `active → deletion_requested → blocked_from_use → deleted`

1. User opens the memory item and its provenance.
2. User chooses correction, stale/superseded, exclusion or deletion.
3. `[USER APPROVAL]` User confirms scope and downstream impact.
4. System immediately blocks excluded/deletion-pending items from retrieval.
5. Derived artefacts are invalidated or regenerated; connected-system and backup limits are reported honestly.

**Exceptions:** Legal hold, insufficient permission, external provider failure and partial cascade remain visible until resolved. Audit retains metadata, not deleted content.

## Workflow-wide acceptance rules

- Every consequential action has a specific, unexpired approval.
- Every user-visible completion state reflects confirmed internal or provider state.
- Every AI-derived fact, memory or proposal has traceable source evidence or is explicitly unsupported.
- Every failure offers a safe next step and never leaks another organisation's data.
- Corrections and deletions propagate to search, memory, briefs and future prompts.
- Jobs use leases, idempotency and bounded retries; request handlers do not run unbounded transcription or analysis.

## Related documents

- [User journeys](../01-product/user-journeys.md)
- [Information architecture](information-architecture.md)
- [Target domain model](../03-engineering/target-domain-model.md)
- [AI system blueprint](../04-ai/ai-system-blueprint.md)
- [Integration strategy](../05-integrations/integration-strategy.md)
