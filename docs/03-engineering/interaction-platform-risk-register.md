# Interaction platform risk register

- **Status:** Target risk register for future work orders; owners and ratings must be
  revisited at every implementation/release gate
- **Scale:** Likelihood and impact are qualitative planning assessments, not measured
  probabilities

## Rating guide

- **Likelihood:** Low, Medium or High under the proposed first implementation.
- **Impact:** Moderate, High or Critical to trust, security, usefulness or operation.
- **Detection:** Evidence that reveals the risk early.
- **Fallback:** User-safe degraded behaviour after prevention/mitigation fails.

## Major risks

| Risk                                                          | Likelihood | Impact   | Mitigation                                                                         | Detection                                                                | Fallback                                                               |
| ------------------------------------------------------------- | ---------- | -------- | ---------------------------------------------------------------------------------- | ------------------------------------------------------------------------ | ---------------------------------------------------------------------- |
| Mobile background recording stops under screen lock/OS policy | High       | High     | Do not promise web reliability; native spike and device matrix; chunk locally      | Session heartbeats, gap markers, OS-interruption tests, user reports     | Finalise partial evidence, show gaps and offer immediate debrief       |
| Poor room audio or cross-talk                                 | High       | High     | Microphone guidance, quality preflight, conservative diarisation, source alignment | Audio-quality signals, transcript correction and attribution-error rates | Use reported debrief/visual evidence; keep attribution unknown         |
| Consent refused or withdrawn                                  | High       | Critical | Equal non-recording path, explicit state, immediate stop, policy guidance          | Refusal/withdrawal events and accidental-capture tests                   | Continue interaction privately; use permitted post-interaction capture |
| Consent/notice does not meet jurisdiction/customer policy     | Medium     | Critical | Customer legal review, versioned policy, platform indicators, launch gates         | Policy audit, legal review, incident reports                             | Disable affected capture mode/region; non-recording workflow           |
| Missed or badly timed debrief notification                    | Medium     | High     | Multiple bounded triggers, quiet hours, preferences, local/server dedupe           | Prompt delivery/open latency and dismissal reasons                       | User-triggered capture and one non-intrusive later reminder            |
| Salesperson memory is weak because debrief is delayed         | High       | High     | Prompt promptly, preload objectives/markers, show recency                          | Time-to-evidence versus correction/unknown rates                         | Label recency and reported origin; ask fewer factual-detail questions  |
| Salesperson bias is presented as customer fact                | High       | Critical | Origin badges, claim review, direct/reported separation, corroboration             | Attribution correction/dismissal and evaluation failures                 | Keep reported-only; do not promote as customer-confirmed               |
| AI hallucinates debrief conclusions or quotations             | Medium     | Critical | Strict schemas/citations, no quote without direct fragment, unsupported path       | Unsupported-claim/citation test set and user corrections                 | Reject candidate or show insufficient evidence                         |
| Customer and seller speech are confused in presentations      | High       | Critical | Deck/seller context separation, speaker role, presentation-specific policy         | False buying-signal evaluation and review correction                     | Remove signal; retain only source material and reported observation    |
| Too many debrief questions cause abandonment                  | High       | High     | Rank by value, small cap, reason labels, skip/stop                                 | Question count, duration, abandonment and skip categories                | Save journal as draft and stop asking                                  |
| Notification fatigue across conference interactions           | Medium     | Moderate | Batch event mode, reminder expiry, preferences                                     | Dismissal/mute rate and multiple-prompt incidents                        | Silent inbox of uncaptured interactions; user-triggered debrief        |
| Storage cost grows with raw media/visuals                     | Medium     | High     | Per-tenant quotas, short raw retention, lifecycle rules, size limits               | Bytes/duration and cost by tenant/source, orphan reports                 | Disable new large capture; retain validated text/claims per policy     |
| Transcription/provider cost exceeds value                     | Medium     | High     | Batch first, idempotency, model evaluation, budgets and limits                     | Cost per usable interaction, retry/duplicate usage                       | Debrief-only workflow or cheaper approved provider                     |
| Long sessions exceed processing/lease/provider limits         | Medium     | High     | Chunking, stage jobs, bounded timeouts and resumable provider path                 | Stage duration, lease renewal, timeout and queue-age alerts              | Partial processing, defer, or user-supplied transcript/debrief         |
| Poor connectivity causes lost/duplicate evidence              | High       | High     | Encrypted local manifest, checksums, idempotent chunks, reconciliation             | Missing/conflicting sequence and duplicate receipt metrics               | Preserve local copy, expose partial state, manual retry/discard        |
| Device battery/storage exhaustion                             | Medium     | High     | Preflight, quotas, low-resource warnings, chunk retention policy                   | Client battery/storage events and incomplete-session reason              | Stop safely, retain complete chunks and offer debrief                  |
| Duplicate evidence creates duplicate claims/actions           | Medium     | High     | Source/version fingerprint, idempotency and claim reconciliation                   | Duplicate-source/claim/action counters                                   | Group as corroboration or require merge review                         |
| Contradictory sources are silently overwritten                | Medium     | Critical | First-class conflict edges, source precedence by claim, review                     | Conflict rate and overwrite regression tests                             | Mark disputed/unknown and block dependent action                       |
| Data residency path is incomplete                             | Medium     | Critical | End-to-end region inventory and fail-closed policy                                 | Region trace/audit and deployment checks                                 | Non-processing capture or disable source/provider                      |
| Enterprise bans recording or bots                             | High       | High     | Capture-not-recording positioning; debrief/visual/manual paths                     | Policy configuration and pilot discovery                                 | Use non-recording Companion and approved imports                       |
| Meeting bot is rejected, removed or never admitted            | High       | Moderate | Do not start with bot; visible status and admission timeout                        | Join/admission/removal state and no-source rate                          | Platform import, user-operated capture or debrief                      |
| CRM/imported record conflicts with newer evidence             | Medium     | High     | Field authority, explicit conflict, proposed writes only                           | Conflict and proposal-rejection rates                                    | Leave CRM unchanged and surface reconciliation task                    |
| Sensitive image/email/document leaks into broad output        | Medium     | Critical | Classification, least privilege, redaction/exclusion and output projection         | Access tests, data-loss-prevention review, incident reports              | Revoke access, invalidate derived output and execute deletion response |
| Lost offline device exposes evidence                          | Medium     | Critical | Encryption, short tokens, minimum cache, MDM guidance                              | Device/session revocation and mobile security tests                      | Revoke server access and delete on next contact; incident process      |
| Source deletion leaves derived intelligence active            | Medium     | Critical | Dependency graph and explicit deletion state machine                               | Deletion lineage tests and orphan/reference audits                       | Immediately suppress dependant claims/actions, then reconcile          |
| External provider retains content unexpectedly                | Low/Medium | Critical | Contract/settings review, minimal payload, approved providers                      | Provider configuration audit and deletion receipts                       | Disable provider, incident process, local/mock/debrief fallback        |
| Live provisional intelligence is mistaken for final           | Medium     | High     | Strong provisional labels, separate state/store eligibility                        | UI/API state tests and premature-promotion events                        | Withdraw live output and recompute after final evidence                |
| Overbuilding capture infrastructure before validation         | High       | High     | Sequence debrief/visual first, stage gates and stop criteria                       | Roadmap spend versus adoption/usable-intelligence metrics                | Stop after validated stage; keep simpler workflow                      |
| Interaction migration destabilises mature Meeting paths       | Medium     | Critical | Additive link, adapters, shadow reads, no historical rewrite                       | Meeting/Workspace/Brain regression and reconciliation                    | Disable Interaction surface and continue Meeting-only path             |
| Cross-tenant evidence or storage reference                    | Low        | Critical | Composite keys, explicit predicates, forced RLS, server-derived object keys        | Adversarial tenant/RLS/signed-URL tests                                  | Fail closed, revoke grants, incident response                          |

## Cross-cutting detection dashboard

Operators need content-free measures for:

- capture-session completion, partial/gap and interruption reason;
- upload reconciliation and orphan object counts;
- queue age, stage latency, provider error/rate limits and bounded retries;
- transcript/attribution correction and unsupported-claim rejection;
- source-origin preservation and conflict rate;
- debrief prompt/duration/abandonment;
- confirmation, correction, dispute and dismissal;
- storage/transcription cost per usable interaction;
- deletion lineage completion and provider/object-store receipts;
- cross-tenant/RLS/signed-grant security test status; and
- feature-disable, provider-disable and rollback readiness.

No dashboard includes raw content or employee performance rankings.

## Review cadence

Every proposed work order must select its applicable risks, assign an accountable
owner, define thresholds and test fallback behaviour. Re-rate after user research,
platform spikes, provider selection, customer legal/security review and production
operational evidence. New source types require a threat/privacy review before
implementation.

## Related documents

- [Interaction security, privacy and consent](interaction-security-privacy-and-consent.md)
- [Mobile companion strategy](../02-design/mobile-companion-strategy.md)
- [Recording and transcription architecture](recording-and-transcription-architecture.md)
- [Interaction Intelligence roadmap](../06-roadmap/interaction-intelligence-roadmap.md)
