# Live Interaction Intelligence security review

## Findings and controls

| Risk                             | Current control                                                                                                            |
| -------------------------------- | -------------------------------------------------------------------------------------------------------------------------- |
| Cross-tenant live stream         | trusted auth tenant context, explicit repository predicates, composite tenant FKs and forced RLS                           |
| Feature bypass                   | server-side `liveInteractionIntelligence` check; both live flags default off                                               |
| Unauthorised capture             | start requires an existing authorised progressive transcript; it grants no recording permission                            |
| External disclosure              | deterministic no-network provider; external flag separately off and unavailable without a reviewed adapter/acknowledgement |
| Partial or out-of-order evidence | contiguous server cursor, bounded overlap, no advance on gaps                                                              |
| Cursor tampering                 | cursor and transcript version are server-owned; client supplies only an idempotency key                                    |
| Duplicate/retry race             | row locking, unique window/trigger constraints and stable signal/subject fingerprints                                      |
| Seller/customer confusion        | controlled speaker roles; customer-intent categories require customer attribution                                          |
| Unknown speaker                  | conservative category allowlist and visible `speaker_uncertain` label                                                      |
| Prompt/transcript injection      | text is data; strict no-action detector contract and tests for injection phrases                                           |
| Browser polling                  | bounded cadence, one in-flight client request, idempotent server processing and safe errors                                |
| Completion race                  | completion locks and freezes active/processing live state in the lifecycle transaction                                     |
| Provisional leakage              | separate tables/contracts; no live write path to final snapshots, Opportunity Workspace or Revenue Brain                   |
| Sensitive logs                   | allowlisted identifiers/counts/codes only; no statements, transcripts, names, objectives, questions or provider payloads   |
| Long-lived provisional data      | 30-day default live expiry, tenant maintenance, source/Interaction/organisation cascading deletion                         |

## Privacy, export and erasure

Export format v11 includes session metadata, bounded provisional statements, source
sequence references, brief progress and reconciliation status. It excludes raw
transcript text, processing windows/fingerprints and provider internals. Meeting,
recording-source, Interaction and organisation deletion remove live dependants before
their referenced parents. Retention marks signals expired and removes them through
the existing bounded maintenance path.

Telemetry names include enable/disable, processing start/completion/failure, signal
counts/dismissal and reconciliation counts. Only metadata allowlisted in
`observability.py` can be emitted.

## Residual limitations

The deterministic provider is suitable for synthetic private-beta evaluation, not a
claim of semantic completeness. Production progressive transcription, provider data
processing terms, residency, consent evidence and performance have not been
approved. Production customer data remains prohibited unless the repository-wide
production controls are separately approved.

No predictive scoring, coaching, task creation, CRM write, notification, native app,
meeting bot, phone interception, biometric ID or autonomous action was introduced.
